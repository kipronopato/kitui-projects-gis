from django import forms
from django.contrib import admin
from django.shortcuts import render, redirect
from django.urls import path
import csv
from .models import Project
from django.contrib.gis.geos import Point
import datetime

class CSVUploadForm(forms.Form):
    csv_file = forms.FileField(label="Upload CSV file")

class ProjectCSVUploadAdmin(admin.ModelAdmin):
    change_list_template = "admin/app/project_csv_upload.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-csv/', self.admin_site.admin_view(self.upload_csv), name='project-upload-csv'),
        ]
        return custom_urls + urls

    def upload_csv(self, request):
        if request.method == "POST":
            form = CSVUploadForm(request.POST, request.FILES)
            if form.is_valid():
                csv_file = form.cleaned_data['csv_file']
                decoded_file = csv_file.read().decode('utf-8').splitlines()
                reader = csv.DictReader(decoded_file)
                for row in reader:
                    location = None
                    lat = row.get('Latitude') or row.get('latitude')
                    lon = row.get('Longitude') or row.get('longitude')
                    if lat and lon:
                        try:
                            location = Point(float(lon), float(lat))
                        except Exception:
                            location = None
                    # Parse dates
                    def parse_date(date_str):
                        if not date_str:
                            return None
                        for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
                            try:
                                return datetime.datetime.strptime(date_str, fmt).date()
                            except Exception:
                                continue
                        return None
                    Project.objects.create(
                        project_id=row.get('Project ID'),
                        name=row.get('Project Name'),
                        sector=row.get('Sector'),
                        status=row.get('Status').lower(),
                        project_manager=row.get('Project Manager'),
                        person_responsible=row.get('Person Responsible'),
                        location=location,
                        county=row.get('County'),
                        start_date=parse_date(row.get('Start Date')),
                        end_date=parse_date(row.get('End Date')),
                        budget=row.get('Budget (KES)'),
                        description='',
                        implementing_agency='',
                        contractor='',
                    )
                self.message_user(request, "Projects uploaded successfully!")
                return redirect('..')
        else:
            form = CSVUploadForm()
        return render(request, "admin/app/project_csv_upload.html", {"form": form})

admin.site.register(Project, ProjectCSVUploadAdmin)
