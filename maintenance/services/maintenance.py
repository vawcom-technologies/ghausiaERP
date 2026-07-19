"""Maintenance business logic services."""

import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger("erp.maintenance")


def calculate_days_since_previous_repair(previous_date, current_date) -> int | None:
    """Calculate days between previous repair restart and new breakdown."""
    if not previous_date or not current_date:
        return None
    delta = current_date.date() if hasattr(current_date, "date") else current_date
    prev = previous_date.date() if hasattr(previous_date, "date") else previous_date
    return (delta - prev).days


def find_previous_breakdown_restart(machine_id: int, before_datetime):
    """Find most recent fixed/closed breakdown restart for a machine."""
    from maintenance.models import MaintenanceJob

    previous = (
        MaintenanceJob.objects.filter(
            machine_id=machine_id,
            maintenance_type="Breakdown",
            status__in=["Fixed", "Closed"],
            is_cancelled=False,
            machine_restarted_datetime__lt=before_datetime,
        )
        .order_by("-machine_restarted_datetime")
        .first()
    )
    return previous


def populate_breakdown_history(job) -> None:
    """Populate previous repair date and days since for breakdown jobs."""
    if job.maintenance_type != "Breakdown":
        return
    previous = find_previous_breakdown_restart(job.machine_id, job.reported_datetime)
    if previous and previous.machine_restarted_datetime:
        job.previous_repair_date = previous.machine_restarted_datetime
        job.days_since_previous_repair = calculate_days_since_previous_repair(
            previous.machine_restarted_datetime, job.reported_datetime
        )


def update_machine_status_on_job_change(job) -> None:
    """Update machine status based on maintenance job state."""
    machine = job.machine
    if job.is_cancelled:
        return

    if job.maintenance_type == "Breakdown" and job.status == "Reported":
        machine.status = "Broken Down"
        machine.save(update_fields=["status"])
        logger.info("Machine %s set to Broken Down", machine.code)
    elif job.status == "In Progress":
        machine.status = "Under Maintenance"
        machine.save(update_fields=["status"])
        logger.info("Machine %s set to Under Maintenance", machine.code)
    elif job.machine_restarted_datetime and job.status in ("Fixed", "Closed"):
        machine.status = "Running"
        machine.save(update_fields=["status"])
        logger.info("Machine %s set to Running", machine.code)


def get_breakdown_duration(job) -> timedelta | None:
    """Calculate breakdown duration from report to machine restart."""
    if not job.reported_datetime or not job.machine_restarted_datetime:
        return None
    return job.machine_restarted_datetime - job.reported_datetime


def get_repair_duration(job) -> timedelta | None:
    """Calculate repair duration from start to completion."""
    if not job.repair_started_datetime or not job.repair_completed_datetime:
        return None
    return job.repair_completed_datetime - job.repair_started_datetime
