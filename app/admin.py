from django.contrib import admin
from .models import Project, ProjectUpdate, CitizenReport

admin.site.register(Project)
admin.site.register(ProjectUpdate)
admin.site.register(CitizenReport)