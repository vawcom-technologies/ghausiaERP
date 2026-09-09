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


class RoleAccessTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User

        from accounts.models import WorkAssignment
        from accounts.permissions import GROUP_ADMIN, GROUP_SUPERVISOR, ensure_role_groups

        groups = ensure_role_groups()
        self.admin = User.objects.create_user("admin_role", password="pass123")
        self.admin.groups.add(groups[GROUP_ADMIN])
        self.supervisor = User.objects.create_user("super_role", password="pass123")
        self.supervisor.groups.add(groups[GROUP_SUPERVISOR])
        self.clerk = User.objects.create_user("clerk_role", password="pass123")
        self.clerk.groups.add(groups[GROUP_DATA_ENTRY])
        WorkAssignment.objects.create(user=self.clerk, module="receiving", assigned_by=self.supervisor)

    def test_permission_helpers(self):
        from accounts.permissions import (
            can_access_module,
            can_assign_work,
            can_delete_records,
            can_manage_users,
            can_permanently_delete,
            can_request_permanent_delete,
            can_view_recycle_bin,
        )

        self.assertTrue(can_delete_records(self.admin))
        self.assertTrue(can_delete_records(self.supervisor))
        self.assertTrue(can_delete_records(self.clerk))
        self.assertTrue(can_view_recycle_bin(self.admin))
        self.assertTrue(can_view_recycle_bin(self.supervisor))
        self.assertTrue(can_view_recycle_bin(self.clerk))
        self.assertTrue(can_permanently_delete(self.admin))
        self.assertFalse(can_permanently_delete(self.supervisor))
        self.assertFalse(can_permanently_delete(self.clerk))
        self.assertFalse(can_request_permanent_delete(self.admin))
        self.assertTrue(can_request_permanent_delete(self.supervisor))
        self.assertFalse(can_request_permanent_delete(self.clerk))
        self.assertTrue(can_assign_work(self.admin))
        self.assertTrue(can_assign_work(self.supervisor))
        self.assertFalse(can_assign_work(self.clerk))
        self.assertTrue(can_manage_users(self.supervisor))
        self.assertTrue(can_access_module(self.clerk, "receiving"))
        self.assertFalse(can_access_module(self.clerk, "dyeing"))
        self.assertTrue(can_access_module(self.supervisor, "dyeing"))

    def test_data_entry_blocked_from_unassigned_module(self):
        self.client.force_login(self.clerk)
        blocked = self.client.get("/production/dyeing/")
        self.assertEqual(blocked.status_code, 302)
        self.assertEqual(blocked.url, "/")
        allowed = self.client.get("/receiving/")
        self.assertEqual(allowed.status_code, 200)

    def test_supervisor_can_create_data_entry_user(self):
        self.client.force_login(self.supervisor)
        response = self.client.post(
            "/users/new/",
            {
                "username": "newclerk",
                "first_name": "New",
                "last_name": "Clerk",
                "password1": "secret1",
                "password2": "secret1",
                "role": "Data Entry User",
                "modules": ["gate_entry", "receiving"],
            },
        )
        self.assertEqual(response.status_code, 302)
        from django.contrib.auth.models import User

        from accounts.models import WorkAssignment

        created = User.objects.get(username="newclerk")
        self.assertTrue(created.groups.filter(name=GROUP_DATA_ENTRY).exists())
        self.assertFalse(created.is_superuser)
        self.assertEqual(
            set(WorkAssignment.objects.filter(user=created).values_list("module", flat=True)),
            {"gate_entry", "receiving"},
        )

    def _deleted_power_reading(self):
        from electricity.models import DailyPowerReading

        row = DailyPowerReading.objects.create(
            record_date=date(2026, 9, 14),
            source_mode=DailyPowerReading.MODE_WAPDA,
            created_by=self.admin,
            updated_by=self.admin,
        )
        row.soft_delete(self.supervisor)
        return row

    def test_supervisor_can_soft_delete_electricity(self):
        from electricity.models import DailyPowerReading

        row = DailyPowerReading.objects.create(
            record_date=date(2026, 9, 15),
            source_mode=DailyPowerReading.MODE_WAPDA,
            created_by=self.admin,
            updated_by=self.admin,
        )
        self.client.force_login(self.supervisor)
        response = self.client.post(f"/electricity/daily/{row.pk}/delete/")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(DailyPowerReading.objects.filter(pk=row.pk).exists())
        self.assertTrue(DailyPowerReading.objects.deleted().filter(pk=row.pk).exists())

    def test_clerk_can_soft_delete_assigned_job(self):
        from accounts.models import WorkAssignment
        from electricity.models import DailyPowerReading

        WorkAssignment.objects.create(user=self.clerk, module="electricity", assigned_by=self.admin)
        row = DailyPowerReading.objects.create(
            record_date=date(2026, 9, 16),
            source_mode=DailyPowerReading.MODE_WAPDA,
            created_by=self.clerk,
            updated_by=self.clerk,
        )
        self.client.force_login(self.clerk)
        response = self.client.post(f"/electricity/daily/{row.pk}/delete/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(DailyPowerReading.objects.deleted().filter(pk=row.pk).exists())

    def test_recycle_bin_is_visible_by_role(self):
        row = self._deleted_power_reading()
        self.client.force_login(self.admin)
        admin_profile = self.client.get("/profile/")
        self.assertContains(admin_profile, "Recently Deleted")
        self.assertContains(admin_profile, "Electricity")
        self.assertContains(admin_profile, "Delete permanently")
        self.assertContains(admin_profile, str(row.record_date))

        self.client.force_login(self.supervisor)
        supervisor_profile = self.client.get("/profile/")
        self.assertContains(supervisor_profile, "Recently Deleted")
        self.assertContains(supervisor_profile, "Ask admin to delete")
        self.assertNotContains(supervisor_profile, "Delete permanently")

        self.client.force_login(self.clerk)
        clerk_profile = self.client.get("/profile/")
        self.assertContains(clerk_profile, "Recently Deleted")
        self.assertNotContains(clerk_profile, str(row.record_date))
        self.assertNotContains(clerk_profile, "Delete permanently")
        self.assertNotContains(clerk_profile, "Ask admin to delete")

    def test_clerk_sees_deleted_rows_for_assigned_job(self):
        from accounts.models import WorkAssignment

        WorkAssignment.objects.create(user=self.clerk, module="electricity", assigned_by=self.admin)
        row = self._deleted_power_reading()
        self.client.force_login(self.clerk)
        clerk_profile = self.client.get("/profile/")
        self.assertContains(clerk_profile, str(row.record_date))
        self.assertContains(clerk_profile, "Restore")
        self.assertNotContains(clerk_profile, "Delete permanently")

    def test_supervisor_permanent_delete_asks_admin(self):
        from accounts.models import PermanentDeleteRequest
        from electricity.models import DailyPowerReading

        row = self._deleted_power_reading()
        self.client.force_login(self.supervisor)
        response = self.client.post(f"/profile/purge/electricity_daily/{row.pk}/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(DailyPowerReading.objects.deleted().filter(pk=row.pk).exists())
        req = PermanentDeleteRequest.objects.get(model_key="electricity_daily", object_pk=row.pk)
        self.assertEqual(req.status, PermanentDeleteRequest.STATUS_PENDING)
        self.assertEqual(req.requested_by, self.supervisor)

        self.client.force_login(self.admin)
        admin_profile = self.client.get("/profile/")
        self.assertContains(admin_profile, "Waiting for your approval")
        self.assertContains(admin_profile, "super_role")

        approve = self.client.post(f"/profile/delete-request/{req.pk}/", {"decision": "approve"})
        self.assertEqual(approve.status_code, 302)
        self.assertFalse(DailyPowerReading.all_objects.filter(pk=row.pk).exists())
        req.refresh_from_db()
        self.assertEqual(req.status, PermanentDeleteRequest.STATUS_APPROVED)

    def test_admin_can_purge_deleted_record(self):
        from electricity.models import DailyPowerReading

        row = self._deleted_power_reading()
        self.client.force_login(self.admin)
        response = self.client.post(f"/profile/purge/electricity_daily/{row.pk}/")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(DailyPowerReading.all_objects.filter(pk=row.pk).exists())

    def test_clerk_cannot_purge_or_ask_admin(self):
        row = self._deleted_power_reading()
        self.client.force_login(self.clerk)
        purge = self.client.post(f"/profile/purge/electricity_daily/{row.pk}/")
        self.assertEqual(purge.status_code, 403)
        ask = self.client.post(f"/profile/ask-delete/electricity_daily/{row.pk}/")
        self.assertEqual(ask.status_code, 403)

    def test_clerk_can_restore_assigned_deleted_row(self):
        from accounts.models import WorkAssignment
        from electricity.models import DailyPowerReading

        WorkAssignment.objects.create(user=self.clerk, module="electricity", assigned_by=self.admin)
        row = self._deleted_power_reading()
        self.client.force_login(self.clerk)
        response = self.client.post(f"/profile/restore/electricity_daily/{row.pk}/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(DailyPowerReading.objects.filter(pk=row.pk).exists())

    def test_clerk_cannot_restore_unassigned_deleted_row(self):
        row = self._deleted_power_reading()
        self.client.force_login(self.clerk)
        response = self.client.post(f"/profile/restore/electricity_daily/{row.pk}/")
        self.assertEqual(response.status_code, 403)

    def test_create_job_station_accounts(self):
        self.client.force_login(self.admin)
        response = self.client.post("/users/job-accounts/")
        self.assertEqual(response.status_code, 302)
        from django.contrib.auth.models import User

        from accounts.models import WorkAssignment

        gate = User.objects.get(username="gateentry")
        self.assertTrue(gate.check_password("gate123"))
        self.assertEqual(
            set(WorkAssignment.objects.filter(user=gate).values_list("module", flat=True)),
            {"gate_entry"},
        )
        self.client.logout()
        self.client.force_login(gate)
        self.assertEqual(self.client.get("/gate-entry/").status_code, 200)
        self.assertEqual(self.client.get("/receiving/").status_code, 302)

    def test_assignment_dashboard_updates_jobs(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            "/users/assignments/",
            {f"modules_{self.clerk.pk}": ["dyeing", "attendance"]},
        )
        self.assertEqual(response.status_code, 302)
        from accounts.models import WorkAssignment

        self.assertEqual(
            set(WorkAssignment.objects.filter(user=self.clerk).values_list("module", flat=True)),
            {"dyeing", "attendance"},
        )

    def test_staff_lives_on_profile_not_dashboard(self):
        self.client.force_login(self.admin)
        home = self.client.get("/")
        self.assertContains(home, "What is happening in the factory today")
        self.assertContains(home, "Active lots")
        self.assertContains(home, "Lots in production")
        self.assertNotContains(home, "Open staff list")
        self.assertNotContains(home, "No jobs have been assigned to you yet")
        profile = self.client.get("/profile/")
        self.assertContains(profile, "Data-entry staff")
        self.assertContains(profile, "Open staff list")
        self.assertContains(profile, "Recently Deleted")
        self.assertContains(profile, "Only you can delete a record permanently")
        navbar_staff = self.client.get("/").content.decode()
        self.assertNotIn(">Staff</a>", navbar_staff)

        self.client.force_login(self.clerk)
        clerk_home = self.client.get("/")
        self.assertContains(clerk_home, "Your jobs")
        self.assertContains(clerk_home, "Cloth Receiving")
        self.assertContains(clerk_home, "Jobs assigned to you")
        clerk_profile = self.client.get("/profile/")
        self.assertNotContains(clerk_profile, "Open staff list")
        self.assertContains(clerk_profile, "Recently Deleted")
        self.assertContains(clerk_profile, "An administrator must approve")

        self.client.force_login(self.supervisor)
        supervisor_profile = self.client.get("/profile/")
        self.assertContains(supervisor_profile, "Recently Deleted")
        self.assertContains(supervisor_profile, "Ask an administrator")
        self.assertNotContains(supervisor_profile, "Delete permanently")

    def test_mobile_quick_actions_match_assigned_jobs(self):
        self.client.force_login(self.clerk)
        home = self.client.get("/").content.decode()
        self.assertIn("mobile-dock", home)
        self.assertIn('data-mobile-open="mobileJobs"', home)
        self.assertIn("js/mobile_dock.js", home)
        self.assertIn("receiving/export/?today=1", home)
        self.assertNotIn("electricity/daily/export/?today=1", home)
        self.client.force_login(self.admin)
        admin_home = self.client.get("/").content.decode()
        self.assertIn("electricity/daily/export/?today=1", admin_home)
        self.assertIn("Open a job", admin_home)
        excel = self.client.get("/electricity/daily/export/?today=1")
        self.assertEqual(excel.status_code, 200)
        self.assertIn(".xlsx", excel["Content-Disposition"])


class HostingAndLoginTests(TestCase):
    def test_csrf_origins_include_https_railway_host(self):
        from config.hosting import csrf_trusted_origins, parse_host_list

        hosts = parse_host_list("localhost,127.0.0.1", "https://ghausia.up.railway.app")
        self.assertIn("ghausia.up.railway.app", hosts)
        origins = csrf_trusted_origins(hosts)
        self.assertIn("https://ghausia.up.railway.app", origins)
        self.assertIn("http://127.0.0.1:8000", origins)

    def test_login_page_and_sign_in(self):
        from django.contrib.auth.models import User

        User.objects.create_user("admin", password="admin123")
        page = self.client.get("/login/")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "csrfmiddlewaretoken")
        self.assertContains(page, "admin123")
        self.assertContains(page, "no public sign-up")
        self.assertNotContains(page, "mobile-dock")

        rejected = self.client.post("/login/", {"username": "admin", "password": "wrong"})
        self.assertEqual(rejected.status_code, 200)
        self.assertContains(rejected, "admin")

        accepted = self.client.post("/login/", {"username": "admin", "password": "admin123"})
        self.assertEqual(accepted.status_code, 302)
        self.assertEqual(accepted.url, "/")

    def test_new_user_page_requires_sign_in(self):
        page = self.client.get("/users/new/")
        self.assertEqual(page.status_code, 302)
        self.assertIn("/login/", page.url)

    def test_seed_keeps_existing_password(self):
        from django.contrib.auth.models import User
        from django.core.management import call_command

        user = User.objects.create_user("admin", password="keep-me-please")
        call_command("seed_demo_data")
        user.refresh_from_db()
        self.assertTrue(user.check_password("keep-me-please"))
        self.assertTrue(User.objects.get(username="supervisor").check_password("super123"))

    def test_today_export_query_renames_file(self):
        from django.test import RequestFactory
        from django.utils import timezone

        from common.selective_export import export_filename, request_wants_today

        request = RequestFactory().get("/export/", {"today": "1"})
        self.assertTrue(request_wants_today(request))
        self.assertEqual(
            export_filename(request, "gate_entry_export.xlsx"),
            f"gate_entry_export_{timezone.localdate().isoformat()}.xlsx",
        )
