from django import template
register = template.Library()

@register.filter
def dict_get(d, key):
    return d.get(key, [])

@register.filter
def format_date(value, arg="d-m-Y"):
    if not value:
        return ""
    return format(value, arg)