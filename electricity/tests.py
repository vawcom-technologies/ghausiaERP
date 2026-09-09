from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from accounts.permissions import GROUP_ADMIN, GROUP_DATA_ENTRY, ensure_role_groups
from electricity.models import DailyPowerReading
from electricity.services.electricity import monthly_power_report, today_power_reading_exists


class DailyPowerReadingTests(TestCase):
    def setUp(self):
        groups = ensure_role_groups()
        self.admin = User.objects.create_user("elec_admin", password="pass123")
        self.admin.groups.add(groups[GROUP_ADMIN])
        self.clerk = User.objects.create_user("elec_clerk", password="pass123")
        self.clerk.groups.add(groups[GROUP_DATA_ENTRY])
        from accounts.models import WorkAssignment

        WorkAssignment.objects.create(user=self.clerk, module="electricity", assigned_by=self.admin)

    def test_wapda_only_saves_peak_and_offpeak_kwh(self):
        self.client.force_login(self.clerk)
        response = self.client.post(
            "/electricity/daily/new/",
            {
                "record_date": "2026-09-10",
                "source_mode": DailyPowerReading.MODE_WAPDA,
                "wapda_peak_kwh": "120.5",
                "wapda_offpeak_kwh": "80",
                "solar_kwh": "50",
                "peak_hours": "6",
                "offpeak_hours": "10",
                "remarks": "WAPDA day",
            },
        )
        self.assertEqual(response.status_code, 302)
        row = DailyPowerReading.objects.get(record_date=date(2026, 9, 10))
        self.assertEqual(row.source_mode, DailyPowerReading.MODE_WAPDA)
        self.assertEqual(row.wapda_peak_kwh, Decimal("120.5"))
        self.assertEqual(row.wapda_offpeak_kwh, Decimal("80"))
        self.assertEqual(row.solar_kwh, Decimal("0"))
        self.assertEqual(row.wapda_total_kwh, Decimal("200.5"))
        self.assertEqual(row.total_kwh, Decimal("200.5"))
        self.assertEqual(row.total_hours, Decimal("16.00"))

    def test_wapda_and_solar_saves_both_sources(self):
        self.client.force_login(self.clerk)
        response = self.client.post(
            "/electricity/daily/new/",
            {
                "record_date": "2026-09-11",
                "source_mode": DailyPowerReading.MODE_WAPDA_SOLAR,
                "wapda_peak_kwh": "90",
                "wapda_offpeak_kwh": "40",
                "solar_kwh": "25.25",
                "peak_hours": "5",
                "offpeak_hours": "8",
            },
        )
        self.assertEqual(response.status_code, 302)
        row = DailyPowerReading.objects.get(record_date=date(2026, 9, 11))
        self.assertEqual(row.source_mode, DailyPowerReading.MODE_WAPDA_SOLAR)
        self.assertEqual(row.solar_kwh, Decimal("25.25"))
        self.assertEqual(row.total_kwh, Decimal("155.25"))

    def test_same_date_updates_existing_row(self):
        self.client.force_login(self.clerk)
        self.client.post(
            "/electricity/daily/new/",
            {
                "record_date": "2026-09-12",
                "source_mode": DailyPowerReading.MODE_WAPDA,
                "wapda_peak_kwh": "10",
                "wapda_offpeak_kwh": "10",
                "solar_kwh": "0",
                "peak_hours": "2",
                "offpeak_hours": "2",
            },
        )
        self.client.post(
            "/electricity/daily/new/",
            {
                "record_date": "2026-09-12",
                "source_mode": DailyPowerReading.MODE_WAPDA_SOLAR,
                "wapda_peak_kwh": "11",
                "wapda_offpeak_kwh": "12",
                "solar_kwh": "3",
                "peak_hours": "3",
                "offpeak_hours": "4",
            },
        )
        self.assertEqual(DailyPowerReading.objects.filter(record_date=date(2026, 9, 12)).count(), 1)
        row = DailyPowerReading.objects.get(record_date=date(2026, 9, 12))
        self.assertEqual(row.total_kwh, Decimal("26"))
        self.assertEqual(row.source_mode, DailyPowerReading.MODE_WAPDA_SOLAR)

    def test_hours_cannot_exceed_24(self):
        self.client.force_login(self.clerk)
        response = self.client.post(
            "/electricity/daily/new/",
            {
                "record_date": "2026-09-13",
                "source_mode": DailyPowerReading.MODE_WAPDA,
                "wapda_peak_kwh": "1",
                "wapda_offpeak_kwh": "1",
                "solar_kwh": "0",
                "peak_hours": "20",
                "offpeak_hours": "8",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(DailyPowerReading.objects.filter(record_date=date(2026, 9, 13)).exists())

    def test_daily_and_monthly_pages(self):
        DailyPowerReading.objects.create(
            record_date=date(2026, 9, 10),
            source_mode=DailyPowerReading.MODE_WAPDA_SOLAR,
            wapda_peak_kwh=Decimal("10"),
            wapda_offpeak_kwh=Decimal("5"),
            solar_kwh=Decimal("2"),
            peak_hours=Decimal("4"),
            offpeak_hours=Decimal("6"),
            created_by=self.admin,
            updated_by=self.admin,
        )
        self.client.force_login(self.clerk)
        hub = self.client.get("/electricity/")
        self.assertContains(hub, "WAPDA only")
        self.assertContains(hub, "WAPDA + Solar")
        daily = self.client.get("/electricity/daily/")
        self.assertContains(daily, "10")
        self.assertContains(daily, "kWh")
        monthly = self.client.get("/electricity/monthly/?month=9&year=2026")
        self.assertContains(monthly, "Month total")
        self.assertContains(monthly, "17")
        report = monthly_power_report(date(2026, 9, 1))
        self.assertEqual(report["totals"]["total_kwh"], Decimal("17"))
        self.assertTrue(today_power_reading_exists(date(2026, 9, 10)))
        self.assertFalse(today_power_reading_exists(date(2026, 9, 1)))

    def test_clerk_can_soft_delete(self):
        row = DailyPowerReading.objects.create(
            record_date=date(2026, 9, 14),
            source_mode=DailyPowerReading.MODE_WAPDA,
            created_by=self.admin,
            updated_by=self.admin,
        )
        self.client.force_login(self.clerk)
        response = self.client.post(f"/electricity/daily/{row.pk}/delete/")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(DailyPowerReading.objects.filter(pk=row.pk).exists())
        self.assertTrue(DailyPowerReading.objects.deleted().filter(pk=row.pk).exists())

    def test_export_today(self):
        self.client.force_login(self.admin)
        excel = self.client.get("/electricity/daily/export/?today=1")
        self.assertEqual(excel.status_code, 200)
        self.assertIn(".xlsx", excel["Content-Disposition"])
