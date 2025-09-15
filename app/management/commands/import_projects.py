import csv
import datetime
from django.core.management.base import BaseCommand, CommandError
from django.contrib.gis.geos import Point
from app.models import Project


def safe_parse_date(value):
    """Parse DD/MM/YYYY or YYYY-MM-DD into a Python date, else None."""
    if value and value.strip().lower() not in ["null", "none", "nan", ""]:
        value = value.strip()
        try:
            # Try DD/MM/YYYY
            return datetime.datetime.strptime(value, "%d/%m/%Y").date()
        except ValueError:
            try:
                # Try ISO YYYY-MM-DD
                return datetime.datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError:
                return None
    return None


def safe_parse_float(value):
    """Return a float if possible, else None."""
    if value and value.strip().lower() not in ["null", "none", "nan", ""]:
        try:
            return float(value.replace(",", ""))  # handle numbers with commas
        except ValueError:
            return None
    return None


class Command(BaseCommand):
    help = "Import projects from a CSV file into the Project model"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str, help="Path to the CSV file")

    def handle(self, *args, **options):
        csv_file = options["csv_file"]

        try:
            with open(csv_file, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)

                count = 0
                for row in reader:
                    # Parse latitude/longitude safely
                    lat = safe_parse_float(row.get("Latitude"))
                    lon = safe_parse_float(row.get("Longitude"))
                    location = (
                        Point(lon, lat) if lat is not None and lon is not None else None
                    )
                    # Only import projects with valid coordinates
                    if lat is not None and lon is not None:
                        Project.objects.create(
                            project_id=row.get("Project ID"),
                            name=row.get("Project Name"),
                            sector=row.get("Sector"),
                            status=row.get("Status"),
                            project_manager=row.get("Project Manager"),
                            person_responsible=row.get("Person Responsible"),
                            latitude=lat,
                            longitude=lon,
                            location=location,
                            county=row.get("County"),
                            start_date=safe_parse_date(row.get("Start Date")),
                            end_date=safe_parse_date(row.get("End Date")),
                            budget=safe_parse_float(row.get("Budget (KES)")),
                            description=row.get("Description"),  # import description
                        )
                        count += 1

        except FileNotFoundError:
            raise CommandError(f"File '{csv_file}' does not exist")

        self.stdout.write(
            self.style.SUCCESS(f"Successfully imported {count} projects")
        )
