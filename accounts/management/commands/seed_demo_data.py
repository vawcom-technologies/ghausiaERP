"""Seed demo data for Ghausia Dyeing."""

from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand

from accounts.permissions import GROUP_ADMIN, GROUP_DATA_ENTRY, GROUP_SUPERVISOR
from electricity.models import ElectricityMeter
from master_data.models import ClothType, Employee, Machine, Material, Vendor


class Command(BaseCommand):
    help = "Create demo users, master data, and sample records for testing."

    def handle(self, *args, **options):
        self.stdout.write("Creating user groups...")
        admin_group, _ = Group.objects.get_or_create(name=GROUP_ADMIN)
        supervisor_group, _ = Group.objects.get_or_create(name=GROUP_SUPERVISOR)
        data_entry_group, _ = Group.objects.get_or_create(name=GROUP_DATA_ENTRY)

        users = [
            ("admin", "admin123", "Admin", "User", "admin@ghausia.local", admin_group, True),
            ("supervisor", "super123", "Supervisor", "User", "supervisor@ghausia.local", supervisor_group, False),
            ("dataentry", "data123", "Data Entry", "User", "dataentry@ghausia.local", data_entry_group, False),
        ]
        for username, password, first_name, last_name, email, group, is_super in users:
            user, created = User.objects.get_or_create(username=username)
            user.first_name = first_name
            user.last_name = last_name
            user.email = email
            user.set_password(password)
            user.is_superuser = is_super
            user.is_staff = is_super or user.is_staff
            user.is_active = True
            user.save()
            user.groups.add(group)
            status = "created" if created else "updated"
            self.stdout.write(f"  User ({status}): {username} / {password} — {user.get_full_name()}")

        vendors = ["Alpha Textiles", "Beta Fabrics", "Gamma Mills"]
        for name in vendors:
            Vendor.objects.get_or_create(name=name, defaults={"contact_person": "Contact", "phone": "0300-0000000", "is_active": True})

        cloth_types = [
            ("PV blend", "PV-BLD"),
            ("Read Pick", "RD-PICK"),
            ("Cotton Grey", "CTN-GRY"),
            ("Polyester", "POL-001"),
            ("Viscose", "VIS-001"),
        ]
        for name, code in cloth_types:
            ClothType.objects.get_or_create(code=code, defaults={"name": name, "is_active": True})

        employees = [("Ahmed Khan", "EMP001", "Production", "Operator"), ("Sara Ali", "EMP002", "Dyeing", "Supervisor")]
        for name, code, dept, role in employees:
            Employee.objects.get_or_create(employee_code=code, defaults={"name": name, "department": dept, "role": role, "is_active": True})

        machines = [
            ("Singeing Unit 1", "SNG-01", "Singeing", "Pre-Treatment"),
            ("Jet Dyeing 1", "JET-01", "Jet Dyeing", "Dyeing"),
            ("Jet Dyeing 2", "JET-02", "Jet Dyeing", "Dyeing"),
            ("Six Chamber 1", "SIX-01", "Six Chamber", "Finishing"),
            ("Calender 1", "CAL-01", "Calender", "Finishing"),
            ("Comfort 1", "CMF-01", "Comfort", "Finishing"),
        ]
        for name, code, mtype, dept in machines:
            Machine.objects.get_or_create(code=code, defaults={"name": name, "machine_type": mtype, "department": dept, "is_active": True})

        materials = [
            ("Caustic Soda", "CHM-001", "Chemical", "Kilogram", 100),
            ("Reactive Red Dye", "DYE-001", "Dye", "Kilogram", 10),
            ("Machine Oil", "OIL-001", "Oil", "Litre", 20),
            ("Grease EP2", "GRS-001", "Grease", "Kilogram", 5),
            ("Motor Bearing", "MNT-001", "Maintenance Item", "Piece", 2),
        ]
        for name, code, cat, unit, min_stock in materials:
            Material.objects.get_or_create(code=code, defaults={"name": name, "category": cat, "unit": unit, "minimum_stock": Decimal(str(min_stock)), "is_active": True})

        ElectricityMeter.objects.get_or_create(meter_number="ELC-001", defaults={"name": "Main Factory Meter", "department": "General", "multiplier": Decimal("1"), "is_active": True})
        ElectricityMeter.objects.get_or_create(meter_number="ELC-002", defaults={"name": "Dyeing Section Meter", "department": "Dyeing", "multiplier": Decimal("10"), "is_active": True})

        self.stdout.write(self.style.SUCCESS("Demo data created successfully."))
        self.stdout.write("Demo passwords: admin/admin123, supervisor/super123, dataentry/data123")
