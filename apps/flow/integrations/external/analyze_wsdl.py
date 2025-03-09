from zeep import Client

wsdl = 'http://195.93.152.206/Aliftestmfo/ws/SiteExchange?wsdl'
client = Client(wsdl=wsdl)

for service in client.wsdl.services.values():
    for port in service.ports.values():
        operations = port.binding._operations.values()
        for operation in operations:
            print(f'Operation: {operation.name}\nInput: {operation.input.signature()}\n')
