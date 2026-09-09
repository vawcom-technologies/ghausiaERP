from django.db import models


class Vendor(models.Model):
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ClothType(models.Model):
    UNIT_CHOICES = [
        ("Metre", "Metre"),
        ("Kg", "Kg"),
    ]

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    default_unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default="Metre")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class Employee(models.Model):
    name = models.CharField(max_length=200)
    employee_code = models.CharField(max_length=50, unique=True)
    department = models.CharField(max_length=100)
    role = models.CharField(max_length=100)
    phone = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Machine(models.Model):
    MACHINE_TYPE_CHOICES = [
        ("Singeing", "Singeing"),
        ("Jet Dyeing", "Jet Dyeing"),
        ("Six Chamber", "Six Chamber"),
        ("Calender", "Calender"),
        ("Comfort", "Comfort"),
        ("Electricity Meter", "Electricity Meter"),
        ("Other", "Other"),
    ]
    STATUS_CHOICES = [
        ("Running", "Running"),
        ("Under Maintenance", "Under Maintenance"),
        ("Broken Down", "Broken Down"),
        ("Inactive", "Inactive"),
    ]

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    machine_type = models.CharField(max_length=50, choices=MACHINE_TYPE_CHOICES)
    department = models.CharField(max_length=100)
    installation_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="Running")
    remarks = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class Material(models.Model):
    CATEGORY_CHOICES = [
        ("Chemical", "Chemical"),
        ("Dye", "Dye"),
        ("Oil", "Oil"),
        ("Grease", "Grease"),
        ("Mechanical", "Mechanical"),
        ("Electrical", "Electrical"),
        ("Maintenance Item", "Maintenance Item"),
        ("Other", "Other"),
    ]
    UNIT_CHOICES = [
        ("Kilogram", "Kilogram"),
        ("Litre", "Litre"),
        ("Gram", "Gram"),
        ("Piece", "Piece"),
        ("Bag", "Bag"),
        ("Drum", "Drum"),
    ]

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES)
    minimum_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"
