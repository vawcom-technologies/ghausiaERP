from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from audit.models import AuditModel
from master_data.models import ClothType, Employee, Machine, Material, Vendor


class ProductionLot(AuditModel):
    STAGE_CHOICES = [
        ("Receiving", "Receiving"),
        ("Singeing", "Singeing"),
        ("Dyeing", "Dyeing"),
        ("Six Chamber", "Six Chamber"),
        ("Calender", "Calender"),
        ("Comfort", "Comfort"),
        ("Finished", "Finished"),
    ]
    STATUS_CHOICES = [
        ("Received", "Received"),
        ("In Production", "In Production"),
        ("On Hold", "On Hold"),
        ("Completed", "Completed"),
        ("Cancelled", "Cancelled"),
    ]

    lot_number = models.CharField(max_length=50, unique=True)
    cloth_receipt = models.OneToOneField(
        "receiving.ClothReceipt", on_delete=models.PROTECT, related_name="production_lot"
    )
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="production_lots")
    cloth_type = models.ForeignKey(ClothType, on_delete=models.PROTECT, related_name="production_lots")
    initial_metres = models.DecimalField(max_digits=12, decimal_places=3)
    initial_weight = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    current_metres = models.DecimalField(max_digits=12, decimal_places=3)
    current_weight = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    current_stage = models.CharField(max_length=50, choices=STAGE_CHOICES, default="Receiving")
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="Received")
    start_date = models.DateField()
    completion_date = models.DateField(null=True, blank=True)
    remarks = models.TextField(blank=True)
    dyeing_completed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-start_date", "-id"]

    def __str__(self) -> str:
        return self.lot_number


class SingeingEntry(AuditModel):
    production_lot = models.ForeignKey(
        ProductionLot, on_delete=models.PROTECT, related_name="singeing_entries"
    )
    process_date = models.DateField()
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, related_name="singeing_entries")
    operator = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="singeing_entries")
    input_metres = models.DecimalField(max_digits=12, decimal_places=3)
    input_weight = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    output_metres = models.DecimalField(max_digits=12, decimal_places=3)
    output_weight = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    damaged_metres = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    supervisor_override = models.BooleanField(default=False)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["-process_date", "-id"]

    def __str__(self) -> str:
        return f"Singeing - {self.production_lot.lot_number}"

    def clean(self) -> None:
        if self.machine.machine_type != "Singeing":
            raise ValidationError({"machine": "Machine must be of type Singeing."})
        if self.output_metres > self.input_metres and not self.supervisor_override:
            raise ValidationError(
                {"output_metres": "Output metres cannot exceed input metres without supervisor override."}
            )


class DyeingBatch(AuditModel):
    batch_number = models.CharField(max_length=50, unique=True)
    production_lot = models.ForeignKey(
        ProductionLot, on_delete=models.PROTECT, related_name="dyeing_batches"
    )
    process_date = models.DateField()
    jet_machine = models.ForeignKey(Machine, on_delete=models.PROTECT, related_name="dyeing_batches")
    operator = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="dyeing_batches")
    input_metres = models.DecimalField(max_digits=12, decimal_places=3)
    input_weight = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    output_metres = models.DecimalField(max_digits=12, decimal_places=3)
    output_weight = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    colour = models.CharField(max_length=100)
    shade = models.CharField(max_length=100, blank=True)
    start_datetime = models.DateTimeField(null=True, blank=True)
    end_datetime = models.DateTimeField(null=True, blank=True)
    supervisor_override = models.BooleanField(default=False)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["-process_date", "-id"]

    def __str__(self) -> str:
        return self.batch_number

    def clean(self) -> None:
        if self.jet_machine.machine_type != "Jet Dyeing":
            raise ValidationError({"jet_machine": "Machine must be of type Jet Dyeing."})
        if self.output_metres > self.input_metres and not self.supervisor_override:
            raise ValidationError(
                {"output_metres": "Output metres cannot exceed input metres without supervisor override."}
            )


class DyeingMaterialUsage(AuditModel):
    dyeing_batch = models.ForeignKey(
        DyeingBatch, on_delete=models.PROTECT, related_name="material_usages"
    )
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="dyeing_usages")
    quantity_used = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.CharField(max_length=20)
    mixture = models.ForeignKey(
        "Mixture", on_delete=models.SET_NULL, null=True, blank=True, related_name="dyeing_usages"
    )
    usage_datetime = models.DateTimeField()
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["-usage_datetime", "-id"]

    def __str__(self) -> str:
        return f"{self.material.name} - {self.dyeing_batch.batch_number}"


class Mixture(AuditModel):
    mixture_number = models.CharField(max_length=50, unique=True)
    dyeing_batch = models.ForeignKey(
        DyeingBatch, on_delete=models.PROTECT, related_name="mixtures"
    )
    name = models.CharField(max_length=200)
    preparation_datetime = models.DateTimeField()
    prepared_by = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="mixtures")
    total_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.CharField(max_length=20)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["-preparation_datetime", "-id"]

    def __str__(self) -> str:
        return self.mixture_number


class MixtureIngredient(AuditModel):
    mixture = models.ForeignKey(Mixture, on_delete=models.PROTECT, related_name="ingredients")
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="mixture_ingredients")
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.CharField(max_length=20)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.material.name} in {self.mixture.mixture_number}"


class SixChamberEntry(AuditModel):
    production_lot = models.ForeignKey(
        ProductionLot, on_delete=models.PROTECT, related_name="six_chamber_entries"
    )
    process_date = models.DateField()
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, related_name="six_chamber_entries")
    operator = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="six_chamber_entries")
    input_metres = models.DecimalField(max_digits=12, decimal_places=3)
    input_weight = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    output_metres = models.DecimalField(max_digits=12, decimal_places=3)
    output_weight = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    temperature = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    machine_speed = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    supervisor_override = models.BooleanField(default=False)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["-process_date", "-id"]

    def clean(self) -> None:
        if self.machine.machine_type != "Six Chamber":
            raise ValidationError({"machine": "Machine must be of type Six Chamber."})
        if self.output_metres > self.input_metres and not self.supervisor_override:
            raise ValidationError(
                {"output_metres": "Output metres cannot exceed input metres without supervisor override."}
            )


class CalenderEntry(AuditModel):
    production_lot = models.ForeignKey(
        ProductionLot, on_delete=models.PROTECT, related_name="calender_entries"
    )
    process_date = models.DateField()
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, related_name="calender_entries")
    operator = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="calender_entries")
    input_metres = models.DecimalField(max_digits=12, decimal_places=3)
    input_weight = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    output_metres = models.DecimalField(max_digits=12, decimal_places=3)
    output_weight = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    width_before = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    width_after = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    supervisor_override = models.BooleanField(default=False)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["-process_date", "-id"]

    def clean(self) -> None:
        if self.machine.machine_type != "Calender":
            raise ValidationError({"machine": "Machine must be of type Calender."})
        if self.output_metres > self.input_metres and not self.supervisor_override:
            raise ValidationError(
                {"output_metres": "Output metres cannot exceed input metres without supervisor override."}
            )


class ComfortEntry(AuditModel):
    production_lot = models.ForeignKey(
        ProductionLot, on_delete=models.PROTECT, related_name="comfort_entries"
    )
    process_date = models.DateField()
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, related_name="comfort_entries")
    operator = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="comfort_entries")
    input_metres = models.DecimalField(max_digits=12, decimal_places=3)
    input_weight = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    output_metres = models.DecimalField(max_digits=12, decimal_places=3)
    output_weight = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    width_before = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    width_after = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    supervisor_override = models.BooleanField(default=False)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["-process_date", "-id"]

    def clean(self) -> None:
        if self.machine.machine_type != "Comfort":
            raise ValidationError({"machine": "Machine must be of type Comfort."})
        if self.output_metres > self.input_metres and not self.supervisor_override:
            raise ValidationError(
                {"output_metres": "Output metres cannot exceed input metres without supervisor override."}
            )


class FinishedStock(AuditModel):
    GRADE_CHOICES = [
        ("Grade A", "Grade A"),
        ("Grade B", "Grade B"),
        ("Rework", "Rework"),
        ("Rejected", "Rejected"),
    ]

    production_lot = models.OneToOneField(
        ProductionLot, on_delete=models.PROTECT, related_name="finished_stock"
    )
    completion_date = models.DateField()
    final_metres = models.DecimalField(max_digits=12, decimal_places=3)
    final_weight = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    number_of_rolls = models.PositiveIntegerField(default=0)
    quality_grade = models.CharField(max_length=20, choices=GRADE_CHOICES)
    accepted_metres = models.DecimalField(max_digits=12, decimal_places=3)
    rejected_metres = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    storage_location = models.CharField(max_length=200, blank=True)
    checked_by = models.ForeignKey(
        Employee, on_delete=models.PROTECT, related_name="finished_stock_checked", null=True, blank=True
    )
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["-completion_date", "-id"]

    def __str__(self) -> str:
        return f"Finished - {self.production_lot.lot_number}"


class ProcessMaterialUsage(AuditModel):
    """Generic material usage for process stages like Six Chamber."""

    STAGE_CHOICES = [
        ("Six Chamber", "Six Chamber"),
        ("Calender", "Calender"),
        ("Comfort", "Comfort"),
    ]

    production_lot = models.ForeignKey(
        ProductionLot, on_delete=models.PROTECT, related_name="process_material_usages"
    )
    stage = models.CharField(max_length=50, choices=STAGE_CHOICES)
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="process_usages")
    quantity_used = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.CharField(max_length=20)
    usage_date = models.DateField()
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["-usage_date", "-id"]

    def __str__(self) -> str:
        return f"{self.material.name} - {self.stage}"
