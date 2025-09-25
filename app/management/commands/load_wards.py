import os
from django.conf import settings
from django.core.management.base import BaseCommand
from django.contrib.gis.utils import LayerMapping
from django.contrib.gis.gdal import DataSource
from app.models import Kenyawards


# Mapping between shapefile fields and model fields
wards_mapping = {
    "county": "county",
    "subcounty": "subcounty",
    "ward": "ward",
    "geom": "MULTIPOLYGON",  # geometry type
}


class Command(BaseCommand):
    help = "Load Kenya Wards shapefile into the database"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("🚀 Starting Wards import process..."))

        # Build absolute path to shapefile
        file = os.path.join(settings.BASE_DIR, "app", "Datasets", "kenya_wards.shp")

        if not os.path.exists(file):
            self.stderr.write(self.style.ERROR(f"❌ File not found: {file}"))
            return

        self.stdout.write(self.style.NOTICE(f"📂 Loading data from: {file}"))

        # Inspect shapefile
        data_source = DataSource(file)
        wards_layer = data_source[0].name
        self.stdout.write(self.style.NOTICE(f"🗂 Detected layer: {wards_layer}"))
        self.stdout.write(self.style.NOTICE(f"📑 Available fields: {data_source[0].fields}"))

        try:
            lm = LayerMapping(
                Kenyawards, file, wards_mapping, layer=wards_layer
            )
            lm.save(strict=True, verbose=True)
            self.stdout.write(self.style.SUCCESS("✅ Wards loaded successfully!"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"⚠️ Import failed: {e}"))
