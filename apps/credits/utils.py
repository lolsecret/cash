from pprint import pprint
from typing import Dict
import re
from operator import add, mul, sub, truediv
from numbers import Real
from num2words import num2words
from num2words.utils import splitbyx, get_digits

from apps.credits import ReportType
from apps.credits.forms import CreditFinanceReportForm
from apps.credits.models import CreditFinance, FinanceReportType


def to_float(value) -> float:
    if isinstance(value, str):
        value = value.replace(',', '.')
    try:
        return float(value)
    except:  # noqa
        return float()


class FinanceReportFactory:
    PREFIX_NAME = 'finance-report'
    FIELD_LIST_MATCH = re.compile(r"(\w+)\[(\d+)\]")
    MONTH_COUNT = 6

    def __init__(self, data=None, initial=None, month_count=6) -> None:
        self.data: dict = data
        self.initial_data: dict = {}
        self.other_data: dict = {}
        self.const_names: dict = {}
        self.month_count: int = self.month_count
        self.cleaned_data = []
        if initial:
            self.prepare(initial)

    @property
    def prefix(self):
        return f"{self.PREFIX_NAME}-"

    @property
    def initial(self):
        if not self.initial_data:
            self.new_initial()

        return self.initial_data

    def prepare(self, initial: dict):
        self.new_initial()

        if isinstance(initial, dict):
            self.initial_data['begin'] = initial.get('begin')
            self.initial_data['end'] = initial.get('end')
            self.initial_data['comment'] = initial.get('comment')

            fields = initial.get('fields')
            if bool(fields):
                self.initial_data['fields'] = fields

    def load_const_names(self):
        self.const_names = {report: {'name': name, 'is_expense': False}
                            for report, name in ReportType.choices}
        for const_name, name in ReportType.choices:
            self.const_names.update({
                const_name: {
                    'const_name': const_name,
                    'name': str(name),
                    'is_expense': False,
                    'data': [0 for _ in range(self.month_count + 1)],
                }
            })

        report_types = FinanceReportType.objects.filter(is_expense=True) \
            .only('name', 'const_name') \
            .order_by('position')

        for report_type in report_types:  # type: FinanceReportType
            self.const_names.update({report_type.const_name: {
                'const_name': report_type.const_name,
                'name': report_type.name,
                'is_expense': True,
                'data': [0 for _ in range(self.month_count + 1)],
            }})

    def new_initial(self):
        self.load_const_names()

        self.initial_data = {
            "prefix": self.prefix,
            "types": self.const_names.copy(),
            "fields": [],
            "begin": None,
            "end": None,
            "comment": "",
            "calculated": [
                ReportType.GAIN.name,
                ReportType.GROSS_PROFIT.name,
                ReportType.TOTAL_BUSINESS_EXPENSES.name,
                ReportType.BUSINESS_PROFIT.name,
                ReportType.NET_PROFIT.name,
                ReportType.NET_RESIDUE_IN_CASH.name,
                ReportType.NET_RESIDUE_IN_PERCENT.name,
            ],
        }

        for report in ReportType.initial_data():
            report['name'] = self.const_names.get(report.get('const_name'), {}).get('name')
            report['is_expense'] = False
            report['data'] = [0 for _ in range(self.month_count + 1)]
            self.initial_data['fields'].append(report)

    def prefix_exists(self):
        for key in self.data.keys():
            if key.startswith(self.prefix):
                return True

        return False

    def is_valid(self):
        if self.prefix_exists() and self.initial:
            for key, value in self.data.items():
                if key.startswith(self.prefix):
                    field = key[len(self.prefix):]

                    match_report = re.match(self.FIELD_LIST_MATCH, field)
                    if match_report:
                        const_name = match_report.group(1)
                        idx = int(match_report.group(2))

                        if const_name in self.const_names:
                            value = to_float(value)

                            filter_by_const_name = lambda report_item: report_item['const_name'] == const_name
                            report = next(filter(filter_by_const_name, self.cleaned_data), None)
                            if report:
                                report['data'][idx] = value

                            else:
                                report: dict = self.const_names.get(const_name)
                                report['data'][idx] = value
                                self.cleaned_data.append(report.copy())
                    else:
                        self.other_data.update({field: value})

            return True
        return False

    def save(self, credit_finance: CreditFinance):
        finance_form = CreditFinanceReportForm(instance=credit_finance, data=self.other_data)
        if finance_form.is_valid():
            finance_form.save()

        credit_finance.finance_report = self.cleaned_data
        credit_finance.save(update_fields=['finance_report'])


class FinReportLineValues(list):
    """
    Helper class for report lines. It accepts data in the form of dictionary.
    Report lines can be added, subtracted, multipled and divided with each
    other and with regular numbers (ints, floats)
    """

    def __init__(self, values, calc_total=True, last_as_total=False):
        if calc_total:
            if last_as_total:
                values[-1] = values[-2]
            else:
                values[-1] = round(sum(values[:-1]) / len(values[:-1]), 2)
        super().__init__(values)

    def _with_other(self, other, func):
        if isinstance(other, FinReportLineValues):
            other_list = other
        else:
            other_list = [other] * len(self)
        values = []
        for a, b in zip(self, other_list):
            try:
                result = round(func(a, b), 2)
            except ZeroDivisionError:
                result = 0
            values.append(result)
        return FinReportLineValues(values, calc_total=False)

    def __add__(self, other):
        return self._with_other(other, add)

    def __iadd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        return self._with_other(other, sub)

    def __isub__(self, other):
        return self.__sub__(other)

    def __mul__(self, other):
        return self._with_other(other, mul)

    def __imul__(self, other):
        return self.__mul__(other)

    def __truediv__(self, other):
        return self._with_other(other, truediv)

    def __itruediv__(self, other):
        return self.__truediv__(other)


class FinReportLine:
    def __init__(self, data, finance_report_month_count, last_as_total=False):
        self._data = data
        self.values = FinReportLineValues(
            [float(value) for value in data["data"][-finance_report_month_count-1:]],
            last_as_total=last_as_total,
        )

    @property
    def data(self):
        self._data['data'] = self.values
        return self._data


def calculate_fin_report(data, finance_report_month_count=FinanceReportFactory.MONTH_COUNT):
    lines: Dict[str, FinReportLine] = {}
    total_business_expenses = FinReportLineValues([0] * (finance_report_month_count + 1))
    for row in data:
        const_name = row.get('const_name')

        last_as_total = False
        if const_name in [ReportType.ESTIMATED_LOAN_INSTALLMENT, ReportType.CURRENT_LOAN_INSTALLMENT]:
            last_as_total = True

        lines[const_name] = FinReportLine(row, finance_report_month_count, last_as_total)
        if row["is_expense"]:
            total_business_expenses += lines[const_name].values

    lines["TOTAL_BUSINESS_EXPENSES"].values = total_business_expenses
    lines["GROSS_PROFIT"].values = lines["REVENUE"].values - lines["NET_COST"].values
    lines["GAIN"].values = lines["GROSS_PROFIT"].values / lines["NET_COST"].values * 100

    lines["BUSINESS_PROFIT"].values = (lines["GROSS_PROFIT"].values - lines["TOTAL_BUSINESS_EXPENSES"].values)

    lines["NET_PROFIT"].values = (
            lines["BUSINESS_PROFIT"].values + lines["OTHER_INCOMES"].values - lines["OTHER_EXPENSES"].values
    )

    lines["NET_RESIDUE_IN_CASH"].values = (
            lines["NET_PROFIT"].values
            - lines["CURRENT_LOAN_INSTALLMENT"].values
            - lines["ESTIMATED_LOAN_INSTALLMENT"].values
    )

    lines["NET_RESIDUE_IN_PERCENT"].values = (lines["NET_RESIDUE_IN_CASH"].values / lines["NET_PROFIT"].values) * 100
    return [line.data for line in lines.values()]


ZERO = 'нөл'

ONES = {
    1: 'Бір',
    2: 'Екі',
    3: 'Үш',
    4: 'Төрт',
    5: 'Бес',
    6: 'Алты',
    7: 'Жеті',
    8: 'Сегіз',
    9: 'Тоғыз',
    0: 'Нөл'
}

TWENTIES = {
    1: 'Он',
    2: 'Жиырма',
    3: 'Отыз',
    4: 'Қырық',
    5: 'Елу',
    6: 'Алпыс',
    7: 'Жетпіс',
    8: 'Сексен',
    9: 'Тоқсан',
}

HUNDRED = 'Жүз'

THOUSANDS = {
    1: 'Мың',
    2: 'миллион',
    3: 'миллиард',
    4: 'триллион',
    5: 'квадриллион',
    6: 'квинтиллион',
    7: 'секстиллион',
    8: 'септиллион',
    9: 'октиллион',
    10: 'нониллион',
}

MONTHS = {
    1: 'Қаңтар',
    2: 'Ақпан',
    3: 'Наурыз',
    4: 'Сәуір',
    5: 'Мамыр',
    6: 'Маусым',
    7: 'Шілде',
    8: 'Тамыз',
    9: 'Қыркүйек',
    10: 'Қазан',
    11: 'Қараша',
    12: 'Желтоқсан',
}

RUSSION_MONTHS = {
    1:'Январь',
    2:'Февраль',
    3:'Март',
    4:'Апрель',
    5:'Май',	
    6:'Июнь',	
    7:'Июль',	
    8:'Август',	
    9:'Сентябрь',	
    10:'Октябрь',	
    11:'Ноябрь',	
    12:'Декабрь',
}

RUSSIAN_FEMININE = {
    1: 'Одна Десятая',
    2: 'Две Десятых',
    3: 'Три Десятых',
    4: 'Четыре Десятых',
    5: 'Пять Десятых',
    6: 'Шесть Десятых',
    7: 'Семь Десятых',
    8: 'Восемь Десятых',
    9: 'Девять Десятых',
    0: 'Ноль Десятых',
}


def int2word(n):
    if n == 0:
        return ZERO

    words = []
    chunks = list(splitbyx(str(n), 3))
    i = len(chunks)
    for x in chunks:
        i -= 1

        if x == 0:
            continue

        n1, n2, n3 = get_digits(x)

        if n3 > 0:
            if n3 > 1:
                words.append(ONES[n3])
            words.append(HUNDRED)

        if n2 > 0:
            words.append(TWENTIES[n2])

        if n1 > 0:
            words.append(ONES[n1])

        if i > 0:
            words.append(THOUSANDS[i])

    return ' '.join(words)


def num2wordskz(number: Real) -> str:
    n = str(number).replace(',', '.')
    pointword = 'үтір'
    if '.' in n:
        left, right = n.split('.')
        return u'%s %s %s' % (
            int2word(int(left)),
            pointword,
            int2word(int(right))
        )
    return int2word(int(n))


def num2wordsfloat(number: Real, lang: str) -> str:
    rounded = round(number, 1)
    int_part = int(rounded)
    decimal_part = int(abs(rounded - int_part) * 10)
    decimal_words = ""
    if lang == 'ru':
        int_words = num2words(int_part, lang=lang).title()
        # if decimal_part:
        decimal_words = f" Целых, {RUSSIAN_FEMININE[decimal_part]}"
    else:
        int_words = num2wordskz(int_part)
        # if decimal_part:
        decimal_words = f" Бүтін, Оннан {ONES[decimal_part]}"
    return int_words + decimal_words


def num2monthkz(number: Real)-> str:
    return str(MONTHS[number]).lower()

def num2monthru(number: Real)-> str:
    return str(RUSSION_MONTHS[number]).lower()
