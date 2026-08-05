import re

from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

register = template.Library()

_STOCK_SPLIT_RE = re.compile(r"\s{2,}|\n+")
STOCK_ATTR_SEP = " || "


@register.filter
def get_field_value(obj, field_name):
    val = getattr(obj, field_name, None)
    if val is None or val == "":
        return "—"
    return val


@register.filter
def stock_items(value):
    """Split stock text on double spaces or newlines into list items."""
    text = str(value or "").strip()
    if not text:
        return []
    items = []
    for part in _STOCK_SPLIT_RE.split(text):
        cleaned = re.sub(r"^\d+\.\s*", "", part.strip())
        if cleaned:
            items.append(cleaned)
    return items


@register.filter
def stock_data_attr(value):
    """Encode stock items for HTML data attributes (safe for getAttribute)."""
    return STOCK_ATTR_SEP.join(stock_items(value))


@register.filter
def stock_preview(value):
    """Single-line plain text for table cells (list only in popup)."""
    items = stock_items(value)
    return ", ".join(items) if items else ""


@register.filter
def stock_list_html(value):
    """Render stock text as a numbered list (or plain text for a single item)."""
    items = stock_items(value)
    if not items:
        return "—"
    if len(items) == 1:
        return conditional_escape(items[0])
    lines = []
    for i, item in enumerate(items, start=1):
        lines.append(
            f'<span class="gate-stock-line">{i}. {conditional_escape(item)}</span>'
        )
    return mark_safe("".join(lines))
