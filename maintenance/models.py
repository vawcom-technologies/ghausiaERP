from django.db import models

from audit.models import AuditModel
from master_data.models import Employee, Machine, Material


class MaintenanceJob(AuditModel):
    MAINTENANCE_TYPE_CHOICES = [
        ("Preventive Maintenance", "Preventive Maintenance"),
        ("Corrective Maintenance", "Corrective Maintenance"),
        ("Breakdown", "Breakdown"),
        ("Inspection", "Inspection"),
    ]
    FAULT_CATEGORY_CHOICES = [
        ("Mechanical", "Mechanical"),
        ("Electrical", "Electrical"),
        ("Hydraulic", "Hydraulic"),
        ("Pneumatic", "Pneumatic"),
        ("Heating", "Heating"),
        ("Motor", "Motor"),
        ("Bearing", "Bearing"),
        ("Sensor", "Sensor"),
        ("Control Panel", "Control Panel"),
        ("Other", "Other"),
    ]
    STATUS_CHOICES = [
        ("Reported", "Reported"),
        ("In Progress", "In Progress"),
        ("Fixed", "Fixed"),
        ("Closed", "Closed"),
    ]

    job_number = models.CharField(max_length=50, unique=True)
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, related_name="maintenance_jobs")
    maintenance_type = models.CharField(max_length=50, choices=MAINTENANCE_TYPE_CHOICES)
    reported_datetime = models.DateTimeField()
    reported_by = models.ForeignKey(
        Employee, on_delete=models.PROTECT, related_name="maintenance_reported"
    )
    fault_category = models.CharField(max_length=50, choices=FAULT_CATEGORY_CHOICES)
    fault_description = models.TextField()
    repair_started_datetime = models.DateTimeField(null=True, blank=True)
    repair_completed_datetime = models.DateTimeField(null=True, blank=True)
    machine_restarted_datetime = models.DateTimeField(null=True, blank=True)
    technician = models.ForeignKey(
        Employee, on_delete=models.PROTECT, related_name="maintenance_technician", null=True, blank=True
    )
    repair_description = models.TextField(blank=True)
    root_cause = models.TextField(blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="Reported")
    previous_repair_date = models.DateTimeField(null=True, blank=True)
    days_since_previous_repair = models.IntegerField(null=True, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["-reported_datetime", "-id"]

    def __str__(self) -> str:
        return self.job_number


class MaintenanceMaterialUsage(AuditModel):
    maintenance_job = models.ForeignKey(
        MaintenanceJob, on_delete=models.PROTECT, related_name="material_usages"
    )
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="maintenance_usages")
    quantity_used = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.CharField(max_length=20)
    usage_date = models.DateField()
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["-usage_date", "-id"]

    def __str__(self) -> str:
        return f"{self.material.name} - {self.maintenance_job.job_number}"
