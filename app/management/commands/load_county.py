import os
from django.conf import settings
from django.core.management.base import BaseCommand
from django.contrib.gis.utils import LayerMapping
from django.contrib.gis.gdal import DataSource
from app.models import KenyaCounty


# ✅ Corrected mapping to match shapefile field names exactly
kenyacounty_mapping = {
    "county": "county",
    "pop_2009": "pop 2009",  # matches shapefile field with space
    "country": "country",
    "geom": "MULTIPOLYGON",  # geometry field
}


class Command(BaseCommand):
    help = "Load Kenya County shapefile into the database"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("🚀 Starting import process..."))

        # Absolute path to shapefile
        file_path = os.path.join(settings.BASE_DIR, "app", "Datasets", "ke_county.shp")

        if not os.path.exists(file_path):
            self.stderr.write(self.style.ERROR(f"❌ File not found: {file_path}"))
            return

        self.stdout.write(self.style.NOTICE(f"📂 Loading data from: {file_path}"))

        # Inspect shapefile before import
        try:
            data_source = DataSource(file_path)
            layer = data_source[0]
            self.stdout.write(self.style.NOTICE(f"🗂 Detected layer: {layer.name}"))
            self.stdout.write(self.style.NOTICE(f"📑 Available fields: {layer.fields}"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"⚠️ Could not read shapefile: {e}"))
            return

        # Import shapefile data into the KenyaCounty model
        try:
            self.stdout.write(self.style.NOTICE("💾 Importing data..."))
            layermapping = LayerMapping(
                KenyaCounty,
                file_path,
                kenyacounty_mapping,
                layer=layer.name,
                transform=False,
                encoding='utf-8',
            )
            layermapping.save(strict=True, verbose=True)
            self.stdout.write(self.style.SUCCESS("✅ Counties loaded successfully!"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"⚠️ Import failed: {e}"))
            return

        # Confirm import
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM app_kenyacounty;")
                count = cursor.fetchone()[0]
            self.stdout.write(self.style.SUCCESS(f"📊 Total counties in database: {count}"))
        except Exception:
            self.stdout.write(self.style.WARNING("ℹ️ Could not verify record count."))
