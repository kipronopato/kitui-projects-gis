import os
from django.conf import settings
from django.core.management.base import BaseCommand
from django.contrib.gis.utils import LayerMapping
from django.contrib.gis.gdal import DataSource
from app.models import KenyaSubCounty


# Field mapping between model and shapefile fields
kenyasubcounty_mapping = {
    "country": "country",
    "county": "county",
    "subcounty": "subcounty",
    "geom": "MULTIPOLYGON",  # geometry type
}


class Command(BaseCommand):
    help = "Load Kenya SubCounty shapefile into the database"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("🚀 Starting SubCounty import process..."))

        # Build absolute path using Django's BASE_DIR
        file = os.path.join(settings.BASE_DIR, "app", "Datasets", "ke_subcounty.shp")

        if not os.path.exists(file):
            self.stderr.write(self.style.ERROR(f"❌ File not found: {file}"))
            return

        self.stdout.write(self.style.NOTICE(f"📂 Loading data from: {file}"))

        # Inspect shapefile
        data_source = DataSource(file)
        kenya_layer = data_source[0].name
        self.stdout.write(self.style.NOTICE(f"🗂 Detected layer: {kenya_layer}"))
        self.stdout.write(self.style.NOTICE(f"📑 Available fields: {data_source[0].fields}"))

        # Run LayerMapping
        try:
            kenya_subcounty_mapping = LayerMapping(
                KenyaSubCounty, file, kenyasubcounty_mapping, layer=kenya_layer
            )
            kenya_subcounty_mapping.save(strict=True, verbose=True)
            self.stdout.write(self.style.SUCCESS("✅ SubCounties loaded successfully!"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"⚠️ Import failed: {e}"))
