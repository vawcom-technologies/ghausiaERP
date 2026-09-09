"""Assignable work areas for data-entry users."""

# (key, label, icon, home_url_name)
WORK_MODULES = (
    ("gate_entry", "Gate Entry", "bi-door-open"),
    ("receiving", "Cloth Receiving", "bi-box-arrow-in-down"),
    ("production_lots", "Production Lots", "bi-diagram-3"),
    ("singeing", "Singeing", "bi-fire"),
    ("dyeing", "Dyeing", "bi-droplet"),
    ("six_chamber", "Six Chamber", "bi-grid-3x3"),
    ("calender", "Calender", "bi-arrows-collapse"),
    ("comfort", "Comfort", "bi-wind"),
    ("finished_stock", "Finished Stock", "bi-box-seam"),
    ("inventory", "Purchases & Stock", "bi-cart-plus"),
    ("chemicals", "Chemicals", "bi-eyedropper"),
    ("electricity", "Electricity", "bi-lightning-charge"),
    ("maintenance", "Maintenance", "bi-tools"),
    ("attendance", "Attendance", "bi-calendar-check"),
)

MODULE_CHOICES = [(key, label) for key, label, _icon in WORK_MODULES]
MODULE_LABELS = {key: label for key, label, _icon in WORK_MODULES}
MODULE_KEYS = [key for key, _label, _icon in WORK_MODULES]

MODULE_HOME_LINKS = {
    "gate_entry": ("gate_entry:sheet", "Record vehicles and material at the gate"),
    "receiving": ("receiving:sheet", "Enter cloth receipts"),
    "production_lots": ("production:lot_list", "Track lots through production"),
    "singeing": ("production:singeing_list", "Singeing process entries"),
    "dyeing": ("production:dyeing_list", "Dyeing batches and materials"),
    "six_chamber": ("production:sixchamber_list", "Six chamber entries"),
    "calender": ("production:calender_list", "Calender entries"),
    "comfort": ("production:comfort_list", "Comfort entries"),
    "finished_stock": ("production:finished_list", "Finished stock records"),
    "inventory": ("inventory:home", "Purchases, adjustments, and stock"),
    "chemicals": ("inventory:stock_chemicals", "Issue slips and chemical stock"),
    "electricity": ("electricity:reading_list", "Daily meter readings"),
    "maintenance": ("maintenance:list", "Breakdowns and repair jobs"),
    "attendance": ("attendance:hub", "Department attendance registers"),
}

# Longest / most specific prefixes first.
MODULE_PATH_PREFIXES = (
    ("/inventory/stock/chemicals/", "chemicals"),
    ("/production/lots/", "production_lots"),
    ("/production/singeing/", "singeing"),
    ("/production/dyeing/", "dyeing"),
    ("/production/mixtures/", "dyeing"),
    ("/production/six-chamber/", "six_chamber"),
    ("/production/calender/", "calender"),
    ("/production/comfort/", "comfort"),
    ("/production/finished/", "finished_stock"),
    ("/gate-entry/", "gate_entry"),
    ("/receiving/", "receiving"),
    ("/inventory/", "inventory"),
    ("/electricity/", "electricity"),
    ("/maintenance/", "maintenance"),
    ("/attendance/", "attendance"),
)


def module_for_path(path: str) -> str | None:
    """Return the work-module key for a request path, or None if not module-scoped."""
    for prefix, module in MODULE_PATH_PREFIXES:
        if path.startswith(prefix):
            return module
    return None
