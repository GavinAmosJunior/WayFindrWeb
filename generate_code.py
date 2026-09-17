import barcode
from barcode.writer import ImageWriter
import csv
import os

# Create output directories
base_output = os.path.join(os.path.dirname(__file__), "barcodes")
locator_dir = os.path.join(base_output, "locators")
sku_dir = os.path.join(base_output, "skus")
os.makedirs(locator_dir, exist_ok=True)
os.makedirs(sku_dir, exist_ok=True)

options = {
    'module_width': 0.4,  
    'module_height': 15.0, 
    'quiet_zone': 6.5,
    'font_size': 10,
    'text_distance': 5.0
}

print("Generating Locator barcodes from CSV...")
source_file = os.path.join(os.path.dirname(__file__), "warehouse_parts_rows.csv")
with open(source_file, newline="", encoding="utf-8") as csv_file:
    locators = sorted({row["locator_id"] for row in csv.DictReader(csv_file) if row["locator_id"]})

for loc in locators:
    my_barcode = barcode.get("code128", loc, writer=ImageWriter())
    filename = os.path.join(locator_dir, loc)
    my_barcode.save(filename, options=options)
    print(f"Saved locator barcode: {loc}.png")

# Hardcoded list of the new SKUs you just inserted (or you can fetch these from Supabase/CSV if stored there)
new_skus = ["SKU-20001", "SKU-20002", "SKU-20003", "SKU-20004", "SKU-20005", "SKU-20006"]

print("\nGenerating Part SKU barcodes for polybags...")
for sku in new_skus:
    my_barcode = barcode.get("code128", sku, writer=ImageWriter())
    filename = os.path.join(sku_dir, sku)
    my_barcode.save(filename, options=options)
    print(f"Saved SKU barcode: {sku}.png")

print("\nDone! Check the 'barcodes/locators' and 'barcodes/skus' folders.")