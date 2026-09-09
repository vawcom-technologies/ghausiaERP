"""Helpers for Excel export of selected list rows."""

from __future__ import annotations

from typing import Any, Callable, Iterable

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect

from common.excel import build_data_export_response


def parse_selected_ids(request: HttpRequest) -> list[int] | None:
    """
    Return selected primary keys from POST/GET.

    - None  → no selection filter (legacy: export all matching the query)
    - []    → client posted an empty selection
    - [..]  → export only these ids
    """
    raw: list[str] = []
    if request.method == "POST":
        raw = request.POST.getlist("ids")
        if not raw:
            csv = (request.POST.get("ids") or "").strip()
            if csv:
                raw = [part.strip() for part in csv.split(",") if part.strip()]
            elif "ids" in request.POST or "export_selected" in request.POST:
                return []
    else:
        raw = request.GET.getlist("ids")
        if not raw:
            csv = (request.GET.get("ids") or "").strip()
            if csv:
                raw = [part.strip() for part in csv.split(",") if part.strip()]

    if not raw:
        return None

    ids: list[int] = []
    seen: set[int] = set()
    for item in raw:
        try:
            pk = int(item)
        except (TypeError, ValueError):
            continue
        if pk not in seen:
            seen.add(pk)
            ids.append(pk)
    return ids


def filter_queryset_by_ids(queryset, ids: list[int] | None):
    """Apply id filter when a selection was provided."""
    if ids is None:
        return queryset
    if not ids:
        return queryset.none()
    return queryset.filter(pk__in=ids)


def ordered_by_ids(queryset, ids: Iterable[int]):
    """Preserve the client's selection order when possible."""
    id_list = list(ids)
    if not id_list:
        return list(queryset)
    by_pk = {obj.pk: obj for obj in queryset.filter(pk__in=id_list)}
    return [by_pk[pk] for pk in id_list if pk in by_pk]


def selective_excel_response(
    request: HttpRequest,
    *,
    queryset,
    headers: list[str],
    row_builder: Callable[[Any], list[Any]],
    filename: str,
    sheet_title: str,
    list_redirect: str,
    list_redirect_kwargs: dict | None = None,
) -> HttpResponse:
    """Shared selected-or-all Excel export response."""
    ids = parse_selected_ids(request)
    if ids is not None and len(ids) == 0:
        messages.error(request, "Select at least one row to export.")
        return redirect(list_redirect, **(list_redirect_kwargs or {}))

    qs = filter_queryset_by_ids(queryset, ids)
    objects = ordered_by_ids(qs, ids) if ids is not None else list(qs)
    return build_data_export_response(
        filename=filename,
        headers=headers,
        rows=[row_builder(obj) for obj in objects],
        sheet_title=sheet_title,
    )
