import barcode
from barcode.writer import ImageWriter
import os

# The exact SKUs we injected into Supabase earlier
parts = [
    "HW-TM-01", "HW-TM-02", "HW-TM-03", "HW-TM-04",
    "HW-MT-01", "HW-MT-02", "HW-MT-03",
    "BB-DH-01", "BB-DH-02", "BB-DH-03",
    "BB-FA-01", "BB-FA-02", "BB-FA-03"
]

# Create a folder to store the images
os.makedirs("barcodes", exist_ok=True)

# Formatting options to make it readable for cameras
options = {
    'module_width': 0.4,  
    'module_height': 15.0, 
    'quiet_zone': 6.5,
    'font_size': 10,
    'text_distance': 5.0
}

print("Generating barcodes...")

for part in parts:
    # Generate Code128 barcode for each SKU
    my_barcode = barcode.get("code128", part, writer=ImageWriter())
    
    # Save it in the /barcodes folder
    filename = f"barcodes/{part}"
    my_barcode.save(filename, options=options)
    print(f"✅ Saved: {filename}.png")

print("Done! Check the 'barcodes' folder.")