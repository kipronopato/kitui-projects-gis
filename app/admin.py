from django.contrib import admin
from .models import Project, ProjectUpdate, CitizenReport, KenyaCounty, KenyaSubCounty, Kenyawards

admin.site.register(Project)
admin.site.register(ProjectUpdate)
admin.site.register(CitizenReport)
admin.site.register(KenyaCounty)
admin.site.register(KenyaSubCounty)
admin.site.register(Kenyawards)