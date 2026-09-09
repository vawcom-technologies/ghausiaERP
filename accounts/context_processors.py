from accounts.modules import MODULE_HOME_LINKS, WORK_MODULES
from accounts.permissions import (
    assigned_modules,
    can_assign_work,
    can_cancel_records,
    can_delete_records,
    can_manage_setup,
    is_administrator,
    is_data_entry,
    is_supervisor,
    is_supervisor_role,
    role_label,
)

_MOBILE_EXCEL = (
    ("gate_entry", "Gate today", "bi-door-open", "gate_entry:export", True),
    ("receiving", "Receiving today", "bi-box-arrow-in-down", "receiving:export", True),
    ("production_lots", "Lots today", "bi-diagram-3", "production:lot_export", True),
    ("inventory", "Purchases today", "bi-cart-plus", "inventory:transaction_export", True),
    ("chemicals", "Chemical stock", "bi-eyedropper", "inventory:chemical_stock_export", False),
    ("electricity", "Electricity today", "bi-lightning-charge", "electricity:reading_export", True),
    ("maintenance", "Maintenance today", "bi-tools", "maintenance:export", True),
)


def erp_roles(request):
    user = getattr(request, "user", None)
    authenticated = bool(user and user.is_authenticated)
    allowed = assigned_modules(user) if authenticated else set()
    mobile_job_links = []
    mobile_excel_links = []
    if authenticated:
        from django.urls import reverse

        for key, label, icon in WORK_MODULES:
            if key in allowed:
                url_name, description = MODULE_HOME_LINKS[key]
                mobile_job_links.append(
                    {
                        "key": key,
                        "label": label,
                        "icon": icon,
                        "url_name": url_name,
                        "description": description,
                    }
                )
        for key, label, icon, url_name, daily in _MOBILE_EXCEL:
            if key in allowed:
                url = reverse(url_name)
                if daily:
                    url = f"{url}?today=1"
                mobile_excel_links.append(
                    {
                        "label": label,
                        "icon": icon,
                        "url": url,
                        "hint": "Today's rows" if daily else "Current list",
                    }
                )
    return {
        "is_administrator": is_administrator(user) if authenticated else False,
        "is_supervisor_role": is_supervisor_role(user) if authenticated else False,
        "is_manager": is_supervisor(user) if authenticated else False,
        "is_data_entry": is_data_entry(user) if authenticated else False,
        "can_manage_staff": can_assign_work(user) if authenticated else False,
        "can_delete_records": can_delete_records(user) if authenticated else False,
        "can_cancel_records": can_cancel_records(user) if authenticated else False,
        "can_manage_setup": can_manage_setup(user) if authenticated else False,
        "allowed_modules": allowed,
        "work_modules": WORK_MODULES,
        "erp_role_label": role_label(user) if authenticated else "",
        "mobile_job_links": mobile_job_links,
        "mobile_excel_links": mobile_excel_links,
    }
