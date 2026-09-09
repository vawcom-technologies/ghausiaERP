"""One data-entry login per factory job (gate, receiving, dyeing, …)."""

from django.contrib.auth.models import User

from accounts.models import WorkAssignment
from accounts.permissions import GROUP_DATA_ENTRY, ensure_role_groups

# username, password, first name, last name, module
JOB_STATION_ACCOUNTS = (
    ("gateentry", "gate123", "Gate", "Entry", "gate_entry"),
    ("receiving", "recv123", "Cloth", "Receiving", "receiving"),
    ("lots", "lots123", "Production", "Lots", "production_lots"),
    ("singeing", "sing123", "Singeing", "Operator", "singeing"),
    ("dyeing", "dye123", "Dyeing", "Operator", "dyeing"),
    ("sixchamber", "six123", "Six Chamber", "Operator", "six_chamber"),
    ("calender", "cal123", "Calender", "Operator", "calender"),
    ("comfort", "comf123", "Comfort", "Operator", "comfort"),
    ("finished", "fin123", "Finished", "Stock", "finished_stock"),
    ("inventory", "inv123", "Inventory", "Store", "inventory"),
    ("chemicals", "chem123", "Chemicals", "Store", "chemicals"),
    ("electricity", "elec123", "Electricity", "Readings", "electricity"),
    ("maintenance", "maint123", "Maintenance", "Staff", "maintenance"),
    ("attendance", "attn123", "Attendance", "Clerk", "attendance"),
)


def ensure_job_station_accounts(assigned_by=None, reset_passwords=False):
    """Create/update one data-entry user per job. Returns created and updated rows."""
    groups = ensure_role_groups()
    data_entry = groups[GROUP_DATA_ENTRY]
    created, updated = [], []

    for username, password, first_name, last_name, module in JOB_STATION_ACCOUNTS:
        user, was_created = User.objects.get_or_create(username=username)
        user.first_name = first_name
        user.last_name = last_name
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False
        if was_created or reset_passwords:
            user.set_password(password)
        user.save()
        user.groups.set([data_entry])
        WorkAssignment.objects.filter(user=user).exclude(module=module).delete()
        WorkAssignment.objects.get_or_create(
            user=user,
            module=module,
            defaults={"assigned_by": assigned_by},
        )
        row = {
            "username": username,
            "password": password,
            "name": user.get_full_name(),
            "module": module,
            "created": was_created,
        }
        (created if was_created else updated).append(row)
    return created, updated
