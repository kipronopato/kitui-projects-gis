from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from app.models import Project

class Command(BaseCommand):
    help = 'Set location field for all projects with valid latitude and longitude'

    def handle(self, *args, **options):
        updated = 0
        for project in Project.objects.all():
            if project.latitude is not None and project.longitude is not None:
                project.location = Point(float(project.longitude), float(project.latitude))
                project.save()
                updated += 1
        self.stdout.write(self.style.SUCCESS(f'Successfully updated location for {updated} projects'))
