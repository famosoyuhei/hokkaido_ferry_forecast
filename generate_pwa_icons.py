#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate PWA icons for ferry forecast app
Creates 192x192 and 512x512 PNG icons
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

def create_ferry_icon(size: int, output_path: str):
    """Create a ferry icon with gradient background"""

    # Create image with gradient background (RGBA for transparency)
    img = Image.new('RGBA', (size, size))
    draw = ImageDraw.Draw(img)

    # Draw gradient background (purple gradient)
    for y in range(size):
        # Calculate gradient color (from #667eea to #764ba2)
        ratio = y / size
        r = int(102 + (118 - 102) * ratio)
        g = int(126 + (75 - 126) * ratio)
        b = int(234 + (162 - 234) * ratio)
        draw.line([(0, y), (size, y)], fill=(r, g, b))

    # Draw ferry icon (simplified ship shape)
    margin = size // 10

    # Ship hull (trapezoid)
    hull_top_y = size * 0.55
    hull_bottom_y = size * 0.75
    hull_left = margin * 2
    hull_right = size - margin * 2

    # Draw hull
    draw.polygon([
        (hull_left + margin, hull_top_y),
        (hull_right - margin, hull_top_y),
        (hull_right, hull_bottom_y),
        (hull_left, hull_bottom_y)
    ], fill='white')

    # Draw cabin (rectangle on top of hull)
    cabin_height = size * 0.15
    cabin_width = size * 0.4
    cabin_x = (size - cabin_width) / 2
    cabin_y = hull_top_y - cabin_height

    draw.rectangle([
        (cabin_x, cabin_y),
        (cabin_x + cabin_width, hull_top_y)
    ], fill='white')

    # Draw smokestack
    stack_width = size * 0.08
    stack_height = size * 0.08
    stack_x = cabin_x + cabin_width * 0.7
    stack_y = cabin_y - stack_height

    draw.rectangle([
        (stack_x, stack_y),
        (stack_x + stack_width, cabin_y)
    ], fill='white')

    # Draw windows on cabin
    window_size = size * 0.04
    window_margin = size * 0.02
    for i in range(3):
        window_x = cabin_x + window_margin + i * (window_size + window_margin)
        window_y = cabin_y + window_margin
        draw.rectangle([
            (window_x, window_y),
            (window_x + window_size, window_y + window_size)
        ], fill='#667eea')

    # Draw waves at bottom
    wave_y = hull_bottom_y + margin // 2
    wave_points = []
    num_waves = 8
    for i in range(num_waves + 1):
        x = i * size / num_waves
        y = wave_y + (margin // 3) * (1 if i % 2 == 0 else -1)
        wave_points.append((x, y))

    # Add baseline
    wave_points.append((size, size))
    wave_points.append((0, size))

    draw.polygon(wave_points, fill=(255, 255, 255, 80))

    # Add rounded corners for modern look
    mask = Image.new('L', (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    corner_radius = size // 8
    mask_draw.rounded_rectangle([0, 0, size, size], corner_radius, fill=255)

    # Apply mask
    output = Image.new('RGB', (size, size), (102, 126, 234))
    output.paste(img, (0, 0), mask)

    # Save
    output.save(output_path, 'PNG', quality=95)
    print(f"✅ Created {output_path} ({size}x{size})")

def main():
    """Generate all required PWA icons"""

    print("=" * 60)
    print("PWA ICON GENERATOR")
    print("=" * 60)

    # Ensure static directory exists
    static_dir = Path('static')
    static_dir.mkdir(exist_ok=True)

    # Generate icons
    print("\n📱 Generating PWA icons...")

    try:
        create_ferry_icon(192, str(static_dir / 'icon-192.png'))
        create_ferry_icon(512, str(static_dir / 'icon-512.png'))

        # Create favicon (32x32)
        create_ferry_icon(32, str(static_dir / 'favicon.ico'))

        print("\n✅ All icons generated successfully!")
        print("\nGenerated files:")
        print("  - static/icon-192.png (192x192)")
        print("  - static/icon-512.png (512x512)")
        print("  - static/favicon.ico (32x32)")

    except Exception as e:
        print(f"\n❌ Error generating icons: {e}")
        print("\nNote: This script requires Pillow library.")
        print("Install with: pip install Pillow")
        return 1

    return 0

if __name__ == '__main__':
    exit(main())
