from decimal import Decimal
from datetime import date, timedelta

from django.contrib.auth.models import Group
from django.test import TestCase
from django.utils import timezone

from accounts.permissions import GROUP_DATA_ENTRY
from electricity.models import DailyElectricityReading, ElectricityMeter
from inventory.models import MaterialTransaction
from inventory.services.stock import create_material_transaction, get_material_stock, reverse_material_transaction
from maintenance.models import MaintenanceJob, MaintenanceMaterialUsage
from maintenance.services.maintenance import populate_breakdown_history
from master_data.models import ClothType, Employee, Machine, Material, Vendor
from production.models import DyeingBatch, DyeingMaterialUsage, FinishedStock, ProductionLot, SingeingEntry
from production.services.calculations import calculate_shrinkage
from production.services.lot import create_production_lot_from_receipt, complete_finished_stock
from receiving.models import ClothReceipt


class ERPWorkflowTests(TestCase):
    def setUp(self):
        self.user = self._create_user("testuser")
        self.vendor = Vendor.objects.create(name="Test Vendor", is_active=True)
        self.cloth = ClothType.objects.create(name="Cotton", code="CTN", is_active=True)
        self.employee = Employee.objects.create(name="Op1", employee_code="E1", department="Prod", role="Op", is_active=True)
        self.singeing_machine = Machine.objects.create(name="S1", code="S1", machine_type="Singeing", department="Pre", is_active=True)
        self.jet_machine = Machine.objects.create(name="J1", code="J1", machine_type="Jet Dyeing", department="Dye", is_active=True)
        self.chemical = Material.objects.create(name="Chem", code="C1", category="Chemical", unit="Kilogram", minimum_stock=0, is_active=True)
        self.oil = Material.objects.create(name="Oil", code="O1", category="Oil", unit="Litre", minimum_stock=0, is_active=True)
        create_material_transaction(material=self.chemical, transaction_type="Purchase", quantity_in=Decimal("100"), quantity_out=Decimal("0"), unit="Kilogram", user=self.user)
        create_material_transaction(material=self.oil, transaction_type="Purchase", quantity_in=Decimal("50"), quantity_out=Decimal("0"), unit="Litre", user=self.user)

    def _create_user(self, username):
        from django.contrib.auth.models import User
        return User.objects.create_user(username=username, password="testpass123")

    def _create_receipt(self, accepted=Decimal("1000")):
        receipt = ClothReceipt(
            receipt_date=date.today(),
            vendor=self.vendor,
            vendor_challan_number="CH-001",
            cloth_type=self.cloth,
            number_of_rolls=10,
            vendor_metres=Decimal("1050"),
            factory_measured_metres=Decimal("1000"),
            vendor_weight="500",
            factory_measured_weight="480",
            rejected_metres=Decimal("0"),
            production_lot_number="LOT-2026-0001",
            received_by=self.employee,
            created_by=self.user,
            updated_by=self.user,
        )
        receipt.calculate_fields()
        receipt.save()
        return receipt

    def test_cloth_receiving_creates_production_lot(self):
        receipt = self._create_receipt()
        lot = create_production_lot_from_receipt(receipt, self.user)
        self.assertEqual(lot.lot_number, "LOT-2026-0001")
        self.assertEqual(lot.initial_metres, Decimal("1000"))
        self.assertEqual(lot.current_stage, "Receiving")

    def test_accepted_metres_calculation(self):
        receipt = self._create_receipt()
        receipt.rejected_metres = Decimal("50")
        receipt.calculate_fields()
        self.assertEqual(receipt.accepted_metres, Decimal("950"))

    def test_singeing_updates_production_lot(self):
        receipt = self._create_receipt()
        lot = create_production_lot_from_receipt(receipt, self.user)
        entry = SingeingEntry.objects.create(
            production_lot=lot, process_date=date.today(), machine=self.singeing_machine,
            operator=self.employee, input_metres=Decimal("1000"), output_metres=Decimal("980"),
            created_by=self.user, updated_by=self.user,
        )
        from production.services.lot import update_lot_after_singeing
        update_lot_after_singeing(entry, self.user)
        lot.refresh_from_db()
        self.assertEqual(lot.current_metres, Decimal("980"))
        self.assertEqual(lot.current_stage, "Dyeing")
        self.assertEqual(lot.status, "In Production")

    def test_dyeing_material_usage_reduces_stock(self):
        lot = create_production_lot_from_receipt(self._create_receipt(), self.user)
        batch = DyeingBatch.objects.create(
            batch_number="LOT-2026-0001-J01", production_lot=lot, process_date=date.today(),
            jet_machine=self.jet_machine, operator=self.employee,
            input_metres=Decimal("980"), output_metres=Decimal("970"), colour="Red",
            created_by=self.user, updated_by=self.user,
        )
        usage = DyeingMaterialUsage.objects.create(
            dyeing_batch=batch, material=self.chemical, quantity_used=Decimal("10"),
            unit="Kilogram", usage_datetime=timezone.now(), created_by=self.user, updated_by=self.user,
        )
        create_material_transaction(
            material=self.chemical, transaction_type="Dyeing Usage", quantity_out=Decimal("10"),
            unit="Kilogram", user=self.user, dyeing_batch=batch,
        )
        self.assertEqual(get_material_stock(self.chemical.id), Decimal("90"))

    def test_cancelling_dyeing_material_restores_stock(self):
        lot = create_production_lot_from_receipt(self._create_receipt(), self.user)
        batch = DyeingBatch.objects.create(
            batch_number="LOT-2026-0001-J01", production_lot=lot, process_date=date.today(),
            jet_machine=self.jet_machine, operator=self.employee,
            input_metres=Decimal("980"), output_metres=Decimal("970"), colour="Red",
            created_by=self.user, updated_by=self.user,
        )
        tx = create_material_transaction(
            material=self.chemical, transaction_type="Dyeing Usage", quantity_out=Decimal("10"),
            unit="Kilogram", user=self.user, dyeing_batch=batch,
        )
        reverse_material_transaction(tx, self.user, "Cancelled")
        self.assertEqual(get_material_stock(self.chemical.id), Decimal("100"))

    def test_maintenance_material_usage_reduces_stock(self):
        machine = self.singeing_machine
        job = MaintenanceJob.objects.create(
            job_number="MNT-2026-0001", machine=machine, maintenance_type="Breakdown",
            reported_datetime=timezone.now(), reported_by=self.employee,
            fault_category="Mechanical", fault_description="Test fault", created_by=self.user, updated_by=self.user,
        )
        create_material_transaction(
            material=self.oil, transaction_type="Maintenance Usage", quantity_out=Decimal("5"),
            unit="Litre", user=self.user, maintenance_job=job,
        )
        self.assertEqual(get_material_stock(self.oil.id), Decimal("45"))

    def test_cancelling_maintenance_usage_restores_stock(self):
        machine = self.singeing_machine
        job = MaintenanceJob.objects.create(
            job_number="MNT-2026-0001", machine=machine, maintenance_type="Breakdown",
            reported_datetime=timezone.now(), reported_by=self.employee,
            fault_category="Mechanical", fault_description="Test fault", created_by=self.user, updated_by=self.user,
        )
        tx = create_material_transaction(
            material=self.oil, transaction_type="Maintenance Usage", quantity_out=Decimal("5"),
            unit="Litre", user=self.user, maintenance_job=job,
        )
        reverse_material_transaction(tx, self.user, "Cancelled")
        self.assertEqual(get_material_stock(self.oil.id), Decimal("50"))

    def test_finished_stock_calculates_shrinkage(self):
        lot = create_production_lot_from_receipt(self._create_receipt(), self.user)
        finished = FinishedStock.objects.create(
            production_lot=lot, completion_date=date.today(), final_metres=Decimal("900"),
            final_weight=Decimal("450"), quality_grade="Grade A", accepted_metres=Decimal("900"),
            created_by=self.user, updated_by=self.user,
        )
        total_loss, shrinkage = calculate_shrinkage(lot.initial_metres, finished.final_metres)
        self.assertEqual(total_loss, Decimal("100"))
        self.assertEqual(shrinkage, Decimal("10"))

    def test_electricity_units_calculation(self):
        meter = ElectricityMeter.objects.create(name="M1", meter_number="M1", department="Gen", multiplier=Decimal("10"))
        reading = DailyElectricityReading(
            reading_date=date.today(), meter=meter,
            opening_reading=Decimal("100"), closing_reading=Decimal("150"), multiplier=Decimal("10"),
            created_by=self.user, updated_by=self.user,
        )
        reading.calculate_units()
        self.assertEqual(reading.units_consumed, Decimal("500"))

    def test_closing_reading_validation(self):
        from django.core.exceptions import ValidationError
        meter = ElectricityMeter.objects.create(name="M2", meter_number="M2", department="Gen", multiplier=Decimal("1"))
        reading = DailyElectricityReading(
            reading_date=date.today(), meter=meter,
            opening_reading=Decimal("200"), closing_reading=Decimal("100"), multiplier=Decimal("1"),
        )
        with self.assertRaises(ValidationError):
            reading.full_clean()

    def test_repeated_breakdown_calculates_days_since_previous(self):
        machine = self.singeing_machine
        prev = MaintenanceJob.objects.create(
            job_number="MNT-2026-0001", machine=machine, maintenance_type="Breakdown",
            reported_datetime=timezone.now() - timedelta(days=30),
            reported_by=self.employee, fault_category="Mechanical", fault_description="Prev",
            status="Closed", machine_restarted_datetime=timezone.now() - timedelta(days=25),
            created_by=self.user, updated_by=self.user,
        )
        new_job = MaintenanceJob(
            job_number="MNT-2026-0002", machine=machine, maintenance_type="Breakdown",
            reported_datetime=timezone.now(), reported_by=self.employee,
            fault_category="Electrical", fault_description="New breakdown",
            created_by=self.user, updated_by=self.user,
        )
        populate_breakdown_history(new_job)
        self.assertIsNotNone(new_job.days_since_previous_repair)
        self.assertGreaterEqual(new_job.days_since_previous_repair, 24)

    def test_data_entry_user_cannot_delete(self):
        from django.contrib.auth.models import User
        de_user = User.objects.create_user("deuser", password="pass")
        group, _ = Group.objects.get_or_create(name=GROUP_DATA_ENTRY)
        de_user.groups.add(group)
        from accounts.permissions import can_cancel_records, can_manage_users
        self.assertFalse(can_manage_users(de_user))
        self.assertFalse(can_cancel_records(de_user))

    def test_cancelled_records_excluded_from_calculations(self):
        lot = create_production_lot_from_receipt(self._create_receipt(), self.user)
        active = SingeingEntry.objects.create(
            production_lot=lot, process_date=date.today(), machine=self.singeing_machine,
            operator=self.employee, input_metres=Decimal("1000"), output_metres=Decimal("980"),
            created_by=self.user, updated_by=self.user,
        )
        cancelled = SingeingEntry.objects.create(
            production_lot=lot, process_date=date.today(), machine=self.singeing_machine,
            operator=self.employee, input_metres=Decimal("500"), output_metres=Decimal("400"),
            is_cancelled=True, created_by=self.user, updated_by=self.user,
        )
        from production.services.calculations import get_stage_summary
        summary = get_stage_summary(lot.singeing_entries.all())
        self.assertEqual(summary["count"], 1)
        self.assertEqual(summary["output_metres"], Decimal("980"))
