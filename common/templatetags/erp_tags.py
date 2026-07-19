from django import template

register = template.Library()


@register.filter
def get_field_value(obj, field_name):
    val = getattr(obj, field_name, None)
    if val is None or val == "":
        return "—"
    return val
