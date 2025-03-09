def service_endpoint_validator(value):
    if value and value[-1] == '/':
        raise ValueError('url should not close with "/"')
