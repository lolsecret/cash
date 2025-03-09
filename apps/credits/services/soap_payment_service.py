import xml.etree.ElementTree as ET

import requests
from django.conf import settings
from django.utils import timezone
from requests.auth import HTTPBasicAuth


class SoapPaymentService:
    url = settings.PAYMENT_1C_WSDL
    user = settings.PAYMENT_1C_USERNAME
    password = ""

    def __init__(self, contract: "CreditContract"):
        self.contract = contract

    @property
    def session(self) -> requests.Session:
        _session = requests.Session()
        encoded_user = self.user.encode("utf-8")
        _session.auth = HTTPBasicAuth(encoded_user, settings.PAYMENT_1C_PASSWORD)
        _session.headers = {'Content-Type': 'text/xml'}

        return _session

    def parse_payment_data(self, tree):  # noqa
        balance = tree.find('.//{http://www.integracia.kz}account_balance').text
        full_name = tree.find('.//{http://www.integracia.kz}fio').text

        contract_list = list()
        contracts = tree.findall('.//{http://www.integracia.kz}contract')
        for contract in contracts:
            contract_number = contract.find('{http://www.integracia.kz}contract_number').text
            planned_payment_date = contract.find('{http://www.integracia.kz}planned_payment_date').text
            planned_payment_amount = contract.find('{http://www.integracia.kz}planned_payment_amount').text
            minimum_amount_of_partial_repayment = contract.find(
                '{http://www.integracia.kz}minimum_amount_of_partial_repayment'
            ).text
            amount_of_debt = contract.find('{http://www.integracia.kz}amount_of_debt').text
            contract_date = contract.find('{http://www.integracia.kz}contract_date').text

            contract_list.append(dict(
                contract_number=contract_number,
                payment_date=planned_payment_date,
                payment_amount=planned_payment_amount,
                minimum_amount_of_partial_repayment=minimum_amount_of_partial_repayment,
                current_debt=amount_of_debt,
                contract_date=contract_date
            ))

        return dict(full_name=full_name, balance=balance, contracts=contract_list)

    def send_check_request(self):
        request_data = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:int="http://www.integracia.kz">
           <soapenv:Header/>
           <soapenv:Body>
              <int:payment>
                 <int:Data>
                    <int:command>check</int:command>
                    <int:txn_id>{self.contract.pk}</int:txn_id>
                    <int:account>{self.contract.borrower.iin}</int:account>
                    <int:sum>{self.contract.params.monthly_payment}</int:sum>
                    <int:pay_type>1</int:pay_type>
                    <int:txn_date>{str(timezone.localdate())}</int:txn_date>
                    <int:contract_number>{self.contract.contract_number}</int:contract_number>
                    <int:contract_date>{str(self.contract.contract_date.date())}</int:contract_date>
                    <int:service_name>Smart Billing</int:service_name>
                 </int:Data>
              </int:payment>
           </soapenv:Body>
        </soapenv:Envelope>
        """

        response = self.session.post(self.url, data=request_data)
        response_text = response.text
        tree = ET.fromstring(response_text)

        return self.parse_payment_data(tree)

    def send_pay_request(self, data):
        request_data = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:int="http://www.integracia.kz">
           <soapenv:Header/>
           <soapenv:Body>
              <int:payment>
                 <int:Data>
                    <int:command>pay</int:command>
                    <int:txn_id>{data['payment_hash']}</int:txn_id>
                    <int:account>{data['iin']}</int:account>
                    <int:sum>{data['payment_amount']}</int:sum>
                    <int:pay_type>1</int:pay_type>
                    <int:txn_date>{str(timezone.localdate())}</int:txn_date>
                    <int:contract_number>{data['contract_number']}</int:contract_number>
                    <int:contract_date>{str(data['contract_date'])}</int:contract_date>
                    <int:service_name>Smart Billing</int:service_name>
                 </int:Data>
              </int:payment>
           </soapenv:Body>
        </soapenv:Envelope>
        """
        response = self.session.post(self.url, data=request_data)
        response_text = response.text
        tree = ET.fromstring(response_text)
        result = tree.find('.//{http://www.integracia.kz}result').text
        comment = tree.find('.//{http://www.integracia.kz}comment').text
        return int(result), comment
