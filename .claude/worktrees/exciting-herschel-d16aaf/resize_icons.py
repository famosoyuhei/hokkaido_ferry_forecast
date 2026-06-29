#!/usr/bin/env python3
"""
Resize app_icon.png to PWA icon sizes (192x192, 512x512)
"""
from PIL import Image
import os

# Paths
base_dir = os.path.dirname(os.path.abspath(__file__))
source_icon = os.path.join(base_dir, "app_icon.png")
static_dir = os.path.join(base_dir, "static")

# Icon sizes for PWA
sizes = [192, 512]

print("Resizing app icon for PWA...")
print(f"Source: {source_icon}")

# Load original image
img = Image.open(source_icon)
print(f"Original size: {img.size}")

# Resize to each required size
for size in sizes:
    # Resize with high-quality resampling
    resized = img.resize((size, size), Image.Resampling.LANCZOS)

    # Save to static folder
    output_path = os.path.join(static_dir, f"icon-{size}.png")
    resized.save(output_path, "PNG", optimize=True)

    # Verify file size
    file_size = os.path.getsize(output_path) / 1024  # KB
    print(f">> Created {output_path} ({file_size:.1f} KB)")

print("\n>> All PWA icons generated successfully!")
print("\nNext steps:")
print("1. Commit and push changes")
print("2. Icons will be used in PWA manifest and home screen")
