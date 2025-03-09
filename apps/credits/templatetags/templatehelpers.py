from django import template

register = template.Library()


@register.simple_tag
def relative_url(value, field_name, url_encode=None):
    url = '?{}={}'.format(field_name, value)
    if url_encode:
        querystring = url_encode.split('&')
        filtered_querystring = filter(lambda p: p.split('=')[0] != field_name, querystring)
        encoded_querystring = '&'.join(filtered_querystring)
        url = '{}&{}'.format(url, encoded_querystring)
    return url


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def by_document_type(documents, document_type_code):
    """Фильтрация загруженных документов по типу"""
    return documents.filter(document_type__code=document_type_code)
