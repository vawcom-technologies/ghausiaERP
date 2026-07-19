"""Common view utilities."""

from django.db.models import Q


def apply_search(queryset, search: str, fields: list[str]):
    """Apply OR search across multiple fields."""
    if not search:
        return queryset
    q = Q()
    for field in fields:
        q |= Q(**{f"{field}__icontains": search})
    return queryset.filter(q)
