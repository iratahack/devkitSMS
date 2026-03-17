#!/usr/bin/env python3
"""
SMS/GG Image Converter Script
==============================

This script converts a PNG image into Sega Master System or Game Gear compatible
palette, tilemap, and tileset binary files. It supports indexed and RGB PNGs,
palette deduplication, tile mirroring, compression, and other options for game
development.

How it works:
- Loads a PNG image and extracts its palette (if indexed) or quantizes colors to
  SMS/GG format.
- Builds a 16-color palette, deduplicating and padding with white unless
  --nosortpal is used.
- Maps image pixels to palette indices.
- Splits the image into tiles (8x8 or 8x16), deduplicates and/or mirrors tiles as
  requested.
- Outputs binary files for palette (.pal), tilemap (.map), and tileset (.tiles).
  Optional PNG tilesheet, ASCII debug output, and compression.

Palette format differences:
  SMS: 1 byte per color, format --BBGGRR (2 bits per channel, 4 levels each).
  GG:  2 bytes per color (little-endian word), format 0000BBBBGGGGRRRR
       (4 bits per channel, 16 levels each).

Command Line Parameters:
------------------------
input_png           Path to input PNG file (indexed or RGB).
output_base         Base name for output files (no extension).
--gamegear          Output Game Gear format palette (12-bit color, 2 bytes/entry).
                    Image should ideally be 160x144 (20x18 tiles) for GG screen.
--luminance-match   Use brightness/luminance for color matching (default: Euclidean distance).
--gamma <float>     Gamma correction for input image (default: 1.0 = no change).
--tiles-png         Output a PNG preview of the tilesheet.
--debug-tiles       Output an ASCII debug file of tiles.
--nomirror          Disable tile mirroring (treat all tiles as unique).
--noremovedups      Disable removal of duplicate tiles (keep all tiles, even if identical).
--tile8x16          Use 8x16 tiles instead of 8x8.
--nosortpal         Do not sort/deduplicate/pad palette; use input palette order after quantization.
--no-map            Do not output a tilemap (.map) file.
--remove-blank      Do not include tiles filled entirely with color index 0 in the tileset;
                    their tilemap entries are set to 0.
--compress          Compress .tiles and .map files using z88dk-zx0 (-f, overwrite originals).

Usage Examples:
---------------
1. Basic SMS conversion (deduplicates palette, uses mirroring):
   python3 sms_converter.py input.png output
   # Produces output.pal, output.map, output.tiles

2. Game Gear conversion (12-bit palette, 2 bytes/color):
   python3 sms_converter.py --gamegear input.png output

3. Use input palette order (no deduplication/padding):
   python3 sms_converter.py --nosortpal input.png output

4. Output tilesheet PNG and debug ASCII file:
   python3 sms_converter.py --tiles-png --debug-tiles input.png output

5. Use 8x16 tiles, disable mirroring and duplicate removal:
   python3 sms_converter.py --tile8x16 --nomirror --noremovedups input.png output

6. Apply gamma correction and luminance matching:
   python3 sms_converter.py --gamma 1.2 --luminance-match input.png output

7. Compress output tiles and map files:
   python3 sms_converter.py --compress input.png output

See help for all options:
   python3 sms_converter.py --help
"""

import sys
import argparse
from pathlib import Path
from PIL import Image
import numpy as np
import math

LEVELS = np.array([0, 85, 170, 255], dtype=np.uint8)
GG_LEVELS = np.array([i * 17 for i in range(16)], dtype=np.uint8)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BIT_HFLIP = 1 << 9
BIT_VFLIP = 1 << 10
ASCII_SHADES = [' ', '.', ':', '-', '=', '+', '*', '#', '%', '@', 'A', 'B', 'C', 'D', 'E', 'F']
TILE_SIZE = 8
SCREEN_WIDTH = 256
SCREEN_HEIGHT = 192

def rgb_to_sms_rgb8(r, g, b, luminance_match=False, gamegear=False):
    levels = GG_LEVELS if gamegear else LEVELS
    if luminance_match:
        y = 0.299 * r + 0.587 * g + 0.114 * b
        min_dist = float('inf')
        best = (0, 0, 0)
        for rr in levels:
            for gg in levels:
                for bb in levels:
                    y_sms = 0.299 * rr + 0.587 * gg + 0.114 * bb
                    dist = abs(y - y_sms)
                    if dist < min_dist:
                        min_dist = dist
                        best = (rr, gg, bb)
        return best
    else:
        min_dist = float('inf')
        best = (0, 0, 0)
        for rr in levels:
            for gg in levels:
                for bb in levels:
                    dist = (int(r)-int(rr))**2 + (int(g)-int(gg))**2 + (int(b)-int(bb))**2
                    if dist < min_dist:
                        min_dist = dist
                        best = (rr, gg, bb)
        return best

def sms_rgb8_to_cram_byte(r, g, b):
    """SMS CRAM: 1 byte, --BBGGRR, 2 bits per channel."""
    ri = max(0, min(3, int(round(r/85))))
    gi = max(0, min(3, int(round(g/85))))
    bi = max(0, min(3, int(round(b/85))))
    return (bi << 4) | (gi << 2) | ri

def gg_rgb8_to_cram_word(r, g, b):
    """GG CRAM: 2 bytes little-endian, 0000BBBBGGGGRRRR, 4 bits per channel."""
    ri = max(0, min(15, int(round(r/17))))
    gi = max(0, min(15, int(round(g/17))))
    bi = max(0, min(15, int(round(b/17))))
    word = (bi << 8) | (gi << 4) | ri
    return word.to_bytes(2, "little")

def build_palette(quant_img, nosortpal=False, input_palette=None, gamegear=False):
    """
    Build a 16-color palette. If nosortpal and input_palette are set, use input_palette order after quantization (no deduplication, no padding). Otherwise, deduplicate and pad to 16 with white.
    """
    if input_palette is not None:
        # Quantize input palette only once here
        quantized = [rgb_to_sms_rgb8(*c, gamegear=gamegear) for c in input_palette]
        if nosortpal:
            # Use quantized palette order, no deduplication, no padding
            return quantized[:16]
        # Deduplicate
        deduped = []
        for qc in quantized:
            if qc not in deduped:
                deduped.append(qc)
            if len(deduped) >= 16:
                break
        # Sort palette for consistency
        deduped = sorted(deduped)
        while len(deduped) < 16:
            deduped.append(WHITE)
        return deduped[:16]
    # No input_palette: deduplicate from quantized image
    flat = quant_img.reshape(-1, 3)
    unique = []
    for c in flat:
        t = tuple(c)
        if t not in unique:
            unique.append(t)
        if len(unique) >= 16:
            break
    # Sort palette for consistency if not nosortpal
    if not nosortpal:
        unique = sorted(unique)
    while len(unique) < 16:
        unique.append(WHITE)
    return unique[:16]

def map_to_indices(quant_img, palette):
    h, w, _ = quant_img.shape
    idx_img = np.empty((h, w), dtype=np.uint8)
    pal_arr = np.array(palette, dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            pix = quant_img[y, x]
            diffs = np.sum((pal_arr - pix) ** 2, axis=1)
            idx_img[y, x] = int(np.argmin(diffs))
    return idx_img

def tile_views(tile):
    orig = tile
    h = np.fliplr(orig)
    v = np.flipud(orig)
    hv = np.flipud(h)
    variants = [orig, h, v, hv]
    bytes_list = [bytes(t.flatten()) for t in variants]
    min_idx = min(range(4), key=lambda i: bytes_list[i])
    canonical = bytes_list[min_idx]
    flags_map = {0: (False, False), 1: (True, False), 2: (False, True), 3: (True, True)}
    return canonical, flags_map[min_idx]

def tiles_to_4bpp_sms_binary(unique_tiles_bytes, tile_shape):
    out = bytearray()
    tile_h, tile_w = tile_shape
    for tbytes in unique_tiles_bytes:
        pix = np.frombuffer(tbytes, dtype=np.uint8).reshape((tile_h, tile_w)) & 0x0F
        for y in range(tile_h):
            row = pix[y]
            b0 = b1 = b2 = b3 = 0
            for x in range(tile_w):
                shift = 7 - x
                p = int(row[x])
                b0 |= ((p >> 0) & 1) << shift
                b1 |= ((p >> 1) & 1) << shift
                b2 |= ((p >> 2) & 1) << shift
                b3 |= ((p >> 3) & 1) << shift
            out.extend([b0, b1, b2, b3])
    return bytes(out)

def write_debug_tiles(unique_tiles_bytes, palette, path, tile_height, tile_width):
    with open(path, "w") as f:
        f.write("=== SMS TILE DEBUG DUMP ===\n")
        f.write("Palette Legend:\n")
        for idx, (r, g, b) in enumerate(palette):
            f.write(f"{idx}: ({r},{g},{b})\n")
        for i, tbytes in enumerate(unique_tiles_bytes):
            f.write(f"\nTile {i}:\n")
            tile = np.frombuffer(tbytes, dtype=np.uint8).reshape(tile_height, tile_width)
            for row in tile:
                f.write(' '.join(f"{v:02}" for v in row) + "\n")

def main():
    parser = argparse.ArgumentParser(description="Convert a PNG to SMS/GG palette/map/tiles.")
    parser.add_argument("--gamegear", action="store_true",
                        help="Output Game Gear format palette (12-bit color, 2 bytes/entry, 0000BBBBGGGGRRRR). "
                             "GG screen is 160x144 (20x18 tiles).")
    parser.add_argument("--luminance-match", action="store_true",
                        help="Use brightness/luminance for color matching instead of Euclidean distance")
    parser.add_argument("input_png")
    parser.add_argument("output_base")
    parser.add_argument("--debug-tiles", action="store_true")
    parser.add_argument("--gamma", type=float, default=1.0,
                        help="Gamma correction for input image (default 1.0 = no change)")
    parser.add_argument("--tiles-png", action="store_true",
                        help="Output a PNG of the tilesheet (default: off)")
    parser.add_argument("--nomirror", action="store_true",
                        help="Disable tile mirroring (treat all tiles as unique, no H/V flip)")
    parser.add_argument("--noremovedups", action="store_true",
                        help="Disable removal of duplicate tiles (keep all tiles, even if identical)")
    parser.add_argument("--tile8x16", action="store_true",
                        help="Use 8x16 tiles instead of 8x8")
    parser.add_argument("--nosortpal", action="store_true",
                        help="Do not sort palette colors (default: sort)")
    parser.add_argument("--no-map", action="store_true",
                        help="Do not output a tilemap (.map) file")
    parser.add_argument("--remove-blank", action="store_true",
                        help="Exclude tiles filled entirely with color index 0 from the tileset; "
                             "their tilemap entries are set to 0")
    parser.add_argument("--compress", action="store_true", help="Compress .tiles and .map with z88dk-zx0 (-f, overwrite)")
    args = parser.parse_args()

    inp = Path(args.input_png)
    base = Path(args.output_base)

    out_pal = base.with_suffix(".pal")
    out_map = base.with_suffix(".map")
    out_png = base.with_name(base.name + "_tiles.png")
    out_bin = base.with_suffix(".tiles")
    out_txt = base.with_suffix(".txt")

    # Open image and extract palette before any conversion
    img_orig = Image.open(inp)
    input_palette = None
    if hasattr(img_orig, 'getpalette') and img_orig.mode == 'P':
        pal = img_orig.getpalette()
        input_palette = [tuple(pal[i:i+3]) for i in range(0, min(16*3, len(pal)), 3)]
    img = img_orig.convert("RGB")
    width, height = img.size

    # Apply gamma correction
    arr = np.array(img, dtype=np.float32) / 255.0
    if args.gamma != 1.0:
        arr = np.power(arr, args.gamma)
    arr = np.clip(arr * 255, 0, 255).astype(np.uint8)

    # Quantize to SMS/GG levels
    quant = np.empty_like(arr)
    for y in range(height):
        for x in range(width):
            quant[y, x] = rgb_to_sms_rgb8(*arr[y, x], luminance_match=args.luminance_match,
                                           gamegear=args.gamegear)

    palette = build_palette(quant, nosortpal=args.nosortpal, input_palette=input_palette,
                            gamegear=args.gamegear)
    idx_img = map_to_indices(quant, palette)

    tile_height = 16 if args.tile8x16 else 8
    tile_width = 8
    tiles_h = height // tile_height
    tiles_w = width // tile_width
    def get_tile(img, ty, tx):
        return img[ty*tile_height:(ty+1)*tile_height, tx*tile_width:(tx+1)*tile_width]

    tile_map_vals = np.zeros((tiles_h, tiles_w), dtype=np.uint16)
    canonical_dict = {}
    unique_tiles_bytes = []

    for ty in range(tiles_h):
        for tx in range(tiles_w):
            tile = get_tile(idx_img, ty, tx)
            if args.remove_blank and not np.any(tile):
                tile_map_vals[ty, tx] = 0
                continue
            if args.nomirror:
                # No mirroring: treat all tiles as unique, no H/V flip
                tile_bytes = bytes(tile.flatten())
                need_h = need_v = False
            else:
                tile_bytes, (need_h, need_v) = tile_views(tile)

            if args.noremovedups:
                # Do not remove duplicates: always add new tile
                tile_index = len(unique_tiles_bytes)
                unique_tiles_bytes.append(tile_bytes)
            else:
                if tile_bytes in canonical_dict:
                    tile_index = canonical_dict[tile_bytes]
                else:
                    tile_index = len(unique_tiles_bytes)
                    canonical_dict[tile_bytes] = tile_index
                    unique_tiles_bytes.append(tile_bytes)

            entry = tile_index & 0x1FF
            if need_h: entry |= BIT_HFLIP
            if need_v: entry |= BIT_VFLIP
            tile_map_vals[ty, tx] = entry

    # Enforce max 448 unique tiles
    if len(unique_tiles_bytes) > 448:
        print(f"{len(unique_tiles_bytes)} unique tiles.")
        raise RuntimeError("Exceeded maximum of 448 unique tiles. Reduce image complexity or enable mirroring/duplicate removal.")

    # write .map
    if not args.no_map:
        with open(out_map, "wb") as f:
            for row in tile_map_vals:
                for v in row:
                    f.write(int(v).to_bytes(2, "little"))

    # write .pal
    with open(out_pal, "wb") as f:
        if args.gamegear:
            for r, g, b in palette:
                f.write(gg_rgb8_to_cram_word(r, g, b))
        else:
            for r, g, b in palette:
                f.write(bytes([sms_rgb8_to_cram_byte(r, g, b)]))

    # binary tileset
    tiles_bin = tiles_to_4bpp_sms_binary(unique_tiles_bytes, (tile_height, tile_width))
    with open(out_bin, "wb") as f: f.write(tiles_bin)

    # Compress tiles and map if requested
    if args.compress:
        import subprocess
        for fname in ([out_bin, out_map] if not args.no_map else [out_bin]):
            try:
                subprocess.run(["z88dk-zx0", "-f", str(fname)], check=True)
            except Exception as e:
                print(f"Compression failed for {fname}: {e}", file=sys.stderr)

    if args.tiles_png:
        # tilesheet PNG preview
        num_tiles = len(unique_tiles_bytes)
        tiles_per_row = 16
        rows = math.ceil(num_tiles / tiles_per_row)
        sheet = Image.new("P", (tiles_per_row*tile_width, rows*tile_height))
        pal_data = []
        for r, g, b in palette: pal_data.extend([r, g, b])
        while len(pal_data) < 256*3: pal_data.extend([0,0,0])
        sheet.putpalette(pal_data[:768])
        for i, tbytes in enumerate(unique_tiles_bytes):
            row = i // tiles_per_row
            col = i % tiles_per_row
            tile_arr = np.frombuffer(tbytes, dtype=np.uint8).reshape((tile_height, tile_width))
            tile_img = Image.fromarray(tile_arr, mode="P")
            tile_img.putpalette(pal_data[:768])
            sheet.paste(tile_img, (col*tile_width, row*tile_height))
        sheet.save(out_png)

    if args.debug_tiles:
        write_debug_tiles(unique_tiles_bytes, palette, out_txt, tile_height, tile_width)

    bytes_per_tile = tile_height * tile_width // 2  # 4bpp, 2 pixels per byte
    target = "Game Gear (12-bit, 2 bytes/color)" if args.gamegear else "SMS (6-bit, 1 byte/color)"
    pal_size = len(palette) * 2 if args.gamegear else len(palette)
    print(f"Target: {target}")
    print("Wrote:")
    print(f"  {out_pal} (palette, {pal_size} bytes)")
    if not args.no_map:
        print(f"  {out_map} (tilemap)")
    if args.tiles_png:
        print(f"  {out_png} (tilesheet preview)")
    print(f"  {out_bin} (tileset, {bytes_per_tile} bytes/tile)")
    if args.debug_tiles: print(f"  {out_txt} (ASCII debug)")
    print(f"Unique tiles: {len(unique_tiles_bytes)} (out of {tiles_w*tiles_h})")

if __name__ == "__main__":
    main()

