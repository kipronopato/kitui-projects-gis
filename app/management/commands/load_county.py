import os
from django.conf import settings
from django.core.management.base import BaseCommand
from django.contrib.gis.utils import LayerMapping
from django.contrib.gis.gdal import DataSource
from app.models import KenyaCounty


# Field mapping between model and shapefile fields
kenyacounty_mapping = {
    "county": "county",
    "pop_2009": "pop_2009",  # ensure this matches your shapefile field name
    "country": "country",
    "geom": "MULTIPOLYGON",  # geometry field
}


class Command(BaseCommand):
    help = "Load Kenya County shapefile into the database"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("🚀 Starting import process..."))

        # Build absolute path using Django's BASE_DIR
        file = os.path.join(settings.BASE_DIR, "app", "Datasets", "ke_county.shp")

        if not os.path.exists(file):
            self.stderr.write(self.style.ERROR(f"❌ File not found: {file}"))
            return

        self.stdout.write(self.style.NOTICE(f"📂 Loading data from: {file}"))

        # Inspect shapefile
        data_source = DataSource(file)
        kenya_counties_layer = data_source[0].name
        self.stdout.write(self.style.NOTICE(f"🗂 Detected layer: {kenya_counties_layer}"))
        self.stdout.write(self.style.NOTICE(f"📑 Available fields: {data_source[0].fields}"))

        # Run LayerMapping
        try:
            kenya_counties_layermapping = LayerMapping(
                KenyaCounty, file, kenyacounty_mapping, layer=kenya_counties_layer
            )
            kenya_counties_layermapping.save(strict=True, verbose=True)
            self.stdout.write(self.style.SUCCESS("✅ Counties loaded successfully!"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"⚠️ Import failed: {e}"))
