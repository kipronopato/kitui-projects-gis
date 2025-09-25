from django.contrib.gis.db import models
from django.contrib.auth.models import User


class Project(models.Model):
    """
    Represents a development project with details such as budget, status,
    location, and responsible personnel.
    """

    STATUS_CHOICES = [
        ("planned", "Planned"),
        ("ongoing", "Ongoing"),
        ("completed", "Completed"),
        ("delayed", "Delayed"),
    ]

    project_id = models.CharField(
        max_length=50, unique=True, blank=True, null=True,
        help_text="Unique identifier for the project (from 'Project ID')"
    )
    name = models.CharField(
        max_length=200,
        help_text="Project name (from 'Project Name')"
    )
    sector = models.CharField(
        max_length=100, blank=True,
        help_text="Sector of the project (from 'Sector')"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="planned",
        help_text="Current project status (from 'Status')"
    )
    project_manager = models.CharField(
        max_length=200, blank=True,
        help_text="Name of the project manager (from 'Project Manager')"
    )
    person_responsible = models.CharField(
        max_length=200, blank=True,
        help_text="Name of person responsible (from 'Person Responsible')"
    )

    # Location details
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        help_text="Explicit latitude value"
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        help_text="Explicit longitude value"
    )
    location = models.PointField(
        geography=True, null=True, blank=True,
        help_text="GIS Point from Latitude/Longitude"
    )
    county = models.CharField(
        max_length=100,
        help_text="County where the project is located"
    )

    # Dates
    start_date = models.DateField(
        help_text="Start date of the project (from 'Start Date')"
    )
    end_date = models.DateField(
        help_text="End date of the project (from 'End Date')"
    )

    # Financials
    budget = models.DecimalField(
        max_digits=18, decimal_places=2,
        help_text="Project budget in KES (from 'Budget (KES)')"
    )

    # Optional details
    description = models.TextField(blank=True, null=True)
    implementing_agency = models.CharField(max_length=200, blank=True)
    contractor = models.CharField(max_length=200, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.project_id or 'N/A'} - {self.name}"


class ProjectUpdate(models.Model):
    """
    Updates and progress reports for a project.
    """

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="updates"
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    progress_percentage = models.IntegerField(default=0)
    photo = models.ImageField(upload_to="project_updates/", blank=True)
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.project.name} - {self.title}"


class CitizenReport(models.Model):
    """
    Citizen-generated reports related to a project.
    """

    REPORT_CHOICES = [
        ("progress", "Progress Report"),
        ("issue", "Issue Report"),
        ("complaint", "Complaint"),
        ("suggestion", "Suggestion"),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="citizen_reports"
    )
    report_type = models.CharField(max_length=50, choices=REPORT_CHOICES)
    description = models.TextField()
    photo = models.ImageField(upload_to="citizen_reports/", blank=True)
    reported_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_approved = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.project.name} - {self.report_type}"


class Kenyawards(models.Model):
    county = models.CharField(max_length=40)
    subcounty = models.CharField(max_length=80)
    ward = models.CharField(max_length=80)
    geom = models.MultiPolygonField(srid=4326)

    def __str__(self):
        return self.ward or f"Ward {self.id}"


class KenyaCounty(models.Model):
    county = models.CharField(max_length=254)
    pop_2009 = models.BigIntegerField()
    country = models.CharField(max_length=5)
    geom = models.MultiPolygonField(srid=4326)

    def __str__(self):
        return self.county or f"County {self.id}"


class KenyaSubCounty(models.Model):
    country = models.CharField(max_length=254)
    province = models.CharField(max_length=254)
    county = models.CharField(max_length=254)
    subcounty = models.CharField(max_length=254)
    geom = models.MultiPolygonField(srid=4326)

    def __str__(self):
        return self.subcounty or f"SubCounty {self.id}"