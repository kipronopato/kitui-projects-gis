import csv
import datetime
from decimal import Decimal, InvalidOperation
from django.core.management.base import BaseCommand, CommandError
from django.contrib.gis.geos import Point
from app.models import Project


class Command(BaseCommand):
    help = "Upload projects from a CSV file into the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_file", type=str, help="The path to the CSV file to upload"
        )

    def handle(self, *args, **options):
        csv_file_path = options["csv_file"]

        def parse_date(date_str):
            """Try to parse date in multiple formats."""
            if not date_str:
                return None
            for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                try:
                    return datetime.datetime.strptime(date_str.strip(), fmt).date()
                except Exception:
                    continue
            return None

        def parse_decimal(val):
            """Convert string to Decimal, cleaning up unwanted chars."""
            if not val:
                return None
            try:
                cleaned = (
                    str(val)
                    .replace(",", "")  # remove thousand separators
                    .replace("“", "")
                    .replace("”", "")
                    .replace('"', "")
                    .strip()
                )
                return Decimal(cleaned) if cleaned else None
            except (InvalidOperation, ValueError):
                return None

        try:
            with open(csv_file_path, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                count_new, count_updated = 0, 0

                for row in reader:
                    # Handle location (lat/lon)
                    location = None
                    lat = row.get("Latitude") or row.get("latitude")
                    lon = row.get("Longitude") or row.get("longitude")
                    if lat and lon:
                        try:
                            location = Point(float(lon), float(lat))
                        except Exception:
                            location = None

                    # Safely parse fields with fallbacks for required NOT NULL fields
                    project_id = row.get("Project ID")

                    start_date = parse_date(row.get("Start Date")) or datetime.date.today()
                    end_date = parse_date(row.get("End Date")) or start_date
                    budget = parse_decimal(row.get("Budget (KES)")) or Decimal("0.00")

                    defaults = {
                        "name": row.get("Project Name") or "Untitled Project",
                        "sector": row.get("Sector") or "",
                        "status": row.get("Status").lower() if row.get("Status") else "planned",
                        "project_manager": row.get("Project Manager") or "",
                        "person_responsible": row.get("Person Responsible") or "",
                        "location": location,
                        "county": row.get("County") or "Unknown",
                        "start_date": start_date,
                        "end_date": end_date,
                        "budget": budget,
                        "description": "",
                        "implementing_agency": "",
                        "contractor": "",
                    }

                    # Update if exists, create if not
                    obj, created = Project.objects.update_or_create(
                        project_id=project_id, defaults=defaults
                    )

                    if created:
                        count_new += 1
                    else:
                        count_updated += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Upload complete: {count_new} new projects, {count_updated} updated."
                    )
                )

        except FileNotFoundError:
            raise CommandError(f'File "{csv_file_path}" does not exist')
        except Exception as e:
            raise CommandError(f"Error processing file: {e}")
