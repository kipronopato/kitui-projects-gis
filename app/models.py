from django.contrib.gis.db import models
from django.contrib.auth.models import User


class Project(models.Model):
    STATUS_CHOICES = [
        ('planned', 'Planned'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('delayed', 'Delayed'),
    ]

    project_id = models.CharField(max_length=50, unique=True, blank=True, null=True)  # from "Project ID"
    name = models.CharField(max_length=200)                     # from "Project Name"
    sector = models.CharField(max_length=100, blank=True)       # from "Sector"
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')  # from "Status"
    project_manager = models.CharField(max_length=200, blank=True)   # from "Project Manager"
    person_responsible = models.CharField(max_length=200, blank=True) # from "Person Responsible"
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)  # explicit latitude
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True) # explicit longitude
    location = models.PointField(geography=True, null=True, blank=True)  # from Lat/Long
    county = models.CharField(max_length=100)                   # from "County"
    start_date = models.DateField()                             # from "Start Date"
    end_date = models.DateField()                               # from "End Date"
    budget = models.DecimalField(max_digits=18, decimal_places=2)  # from "Budget (KES)"
    description = models.TextField(blank=True, null=True)                  # optional extra info
    implementing_agency = models.CharField(max_length=200, blank=True)
    contractor = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.project_id} - {self.name}"

    class Meta:
        ordering = ['-created_at']


class ProjectUpdate(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='updates')
    title = models.CharField(max_length=200)
    description = models.TextField()
    progress_percentage = models.IntegerField(default=0)
    photo = models.ImageField(upload_to='project_updates/', blank=True)
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.project.name} - {self.title}"

    class Meta:
        ordering = ['-created_at']


class CitizenReport(models.Model):
    REPORT_CHOICES = [
        ('progress', 'Progress Report'),
        ('issue', 'Issue Report'),
        ('complaint', 'Complaint'),
        ('suggestion', 'Suggestion'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='citizen_reports')
    report_type = models.CharField(max_length=50, choices=REPORT_CHOICES)
    description = models.TextField()
    photo = models.ImageField(upload_to='citizen_reports/', blank=True)
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.project.name} - {self.report_type}"

    class Meta:
        ordering = ['-created_at']
