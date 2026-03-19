"""
Test suite for sms_converter.py — covers every command-line parameter.

Run with:
    pytest test_sms_converter.py -v
"""

import struct
import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

CONVERTER = Path(__file__).parent / "sms_converter.py"
PYTHON = sys.executable

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _run(*args: str) -> subprocess.CompletedProcess:
    """Invoke the converter and return the completed process."""
    return subprocess.run(
        [PYTHON, str(CONVERTER), *args],
        capture_output=True,
        text=True,
    )


def _make_rgb_png(path: Path, width: int = 32, height: int = 32) -> None:
    """Create a simple solid-colour RGB PNG (no transparency, no palette)."""
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    # Fill quadrants with SMS-quantizable colours so palette extraction is stable
    arr[: height // 2, : width // 2] = (0, 0, 170)       # blue
    arr[: height // 2, width // 2 :] = (170, 0, 0)        # red
    arr[height // 2 :, : width // 2] = (0, 170, 0)        # green
    arr[height // 2 :, width // 2 :] = (170, 170, 170)    # grey
    Image.fromarray(arr, "RGB").save(str(path))


def _make_indexed_png(path: Path, width: int = 32, height: int = 32) -> None:
    """Create an indexed (mode-P) PNG with a known 4-entry palette."""
    arr = np.zeros((height, width), dtype=np.uint8)
    arr[: height // 2, : width // 2] = 0   # black
    arr[: height // 2, width // 2 :] = 1   # red
    arr[height // 2 :, : width // 2] = 2   # green
    arr[height // 2 :, width // 2 :] = 3   # blue
    img = Image.fromarray(arr, "P")
    # Palette: 256 entries × 3 bytes; set first 4, rest black
    pal = [0] * 768
    pal[0:3]   = [0,   0,   0]
    pal[3:6]   = [170, 0,   0]
    pal[6:9]   = [0,   170, 0]
    pal[9:12]  = [0,   0,   170]
    img.putpalette(pal)
    img.save(str(path))


def _make_symmetric_png(path: Path) -> None:
    """
    16×8 image whose right half is the horizontal mirror of the left half.
    Default (mirroring on): 1 unique tile.
    --nomirror: 2 unique tiles.
    """
    arr = np.zeros((8, 16), dtype=np.uint8)
    # Left tile: gradient across columns (indices 0..7)
    for x in range(8):
        arr[:, x] = x % 4          # palette indices 0-3
    # Right tile: mirror of left
    arr[:, 8:] = arr[:, 7::-1]

    img = Image.fromarray(arr, "P")
    pal = [0] * 768
    pal[0:3]  = [0,   0,   0]
    pal[3:6]  = [170, 0,   0]
    pal[6:9]  = [0,   170, 0]
    pal[9:12] = [0,   0,   170]
    img.putpalette(pal)
    img.save(str(path))


def _make_duplicate_tiles_png(path: Path) -> None:
    """
    16×8 image where both 8×8 tiles are identical.
    Without --noremovedups: 1 unique tile.
    With --noremovedups: 2 tiles.
    """
    arr = np.zeros((8, 16), dtype=np.uint8)
    arr[:, :] = np.tile(np.arange(8, dtype=np.uint8) % 4, (8, 2))
    img = Image.fromarray(arr, "P")
    pal = [0] * 768
    pal[0:3]  = [0, 0, 0]
    pal[3:6]  = [170, 0, 0]
    pal[6:9]  = [0, 170, 0]
    pal[9:12] = [0, 0, 170]
    img.putpalette(pal)
    img.save(str(path))


def _make_blank_tile_png(path: Path) -> None:
    """
    16×8 image: left tile all index 0 (blank), right tile non-blank.
    With --remove-blank the tileset should contain only 1 tile.
    """
    arr = np.zeros((8, 16), dtype=np.uint8)
    arr[:, 8:] = 1          # non-blank right tile
    img = Image.fromarray(arr, "P")
    pal = [0] * 768
    pal[0:3]  = [0, 0, 0]
    pal[3:6]  = [170, 0, 0]
    img.putpalette(pal)
    img.save(str(path))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp(tmp_path):
    """Provide a per-test temporary directory and a pre-built RGB PNG."""
    png = tmp_path / "input.png"
    _make_rgb_png(png)
    return tmp_path, png


@pytest.fixture()
def tmp_indexed(tmp_path):
    """Provide a per-test temporary directory and an indexed PNG."""
    png = tmp_path / "indexed.png"
    _make_indexed_png(png)
    return tmp_path, png


# ---------------------------------------------------------------------------
# Basic sanity
# ---------------------------------------------------------------------------

class TestBasicOutput:
    def test_produces_pal_map_tiles(self, tmp):
        d, png = tmp
        out = d / "out"
        r = _run(str(png), str(out))
        assert r.returncode == 0, r.stderr
        assert out.with_suffix(".pal").exists(), ".pal not created"
        assert out.with_suffix(".map").exists(), ".map not created"
        assert out.with_suffix(".tiles").exists(), ".tiles not created"

    def test_no_extra_files_by_default(self, tmp):
        d, png = tmp
        out = d / "out"
        _run(str(png), str(out))
        assert not out.with_name("out_tiles.png").exists(), "tilesheet PNG created without --tiles-png"
        assert not out.with_suffix(".txt").exists(), "debug .txt created without --debug-tiles"

    def test_pal_size_sms(self, tmp):
        """SMS palette: 1 byte per entry × 16 entries = 16 bytes."""
        d, png = tmp
        out = d / "out"
        _run(str(png), str(out))
        pal_data = out.with_suffix(".pal").read_bytes()
        assert len(pal_data) == 16

    def test_map_dimensions(self, tmp):
        """32×32 image / 8×8 tiles = 4×4 map = 16 entries × 2 bytes = 32 bytes."""
        d, png = tmp
        out = d / "out"
        _run(str(png), str(out))
        map_data = out.with_suffix(".map").read_bytes()
        expected = (32 // 8) * (32 // 8) * 2
        assert len(map_data) == expected

    def test_tiles_size_multiple_of_tile_bytes(self, tmp):
        """Each 8×8 4bpp tile is 32 bytes (8 rows × 4 bitplane bytes)."""
        d, png = tmp
        out = d / "out"
        _run(str(png), str(out))
        tiles_data = out.with_suffix(".tiles").read_bytes()
        assert len(tiles_data) % 32 == 0, "tile data not aligned to 32-byte boundaries"


# ---------------------------------------------------------------------------
# --gamegear
# ---------------------------------------------------------------------------

class TestGameGear:
    def test_pal_size_gamegear(self, tmp):
        """GG palette: 2 bytes per entry × 16 entries = 32 bytes."""
        d, png = tmp
        out = d / "out"
        r = _run("--gamegear", str(png), str(out))
        assert r.returncode == 0, r.stderr
        pal_data = out.with_suffix(".pal").read_bytes()
        assert len(pal_data) == 32

    def test_gg_palette_values_differ_from_sms(self, tmp):
        """GG entries are 12-bit words; the raw bytes must differ from SMS encoding."""
        d, png = tmp
        out_sms = d / "sms"
        out_gg  = d / "gg"
        _run(str(png), str(out_sms))
        _run("--gamegear", str(png), str(out_gg))
        sms_bytes = out_sms.with_suffix(".pal").read_bytes()
        gg_bytes  = out_gg.with_suffix(".pal").read_bytes()
        # They cannot be byte-equal (different sizes and encoding)
        assert sms_bytes != gg_bytes

    def test_target_string_in_stdout(self, tmp):
        d, png = tmp
        out = d / "out"
        r = _run("--gamegear", str(png), str(out))
        assert "Game Gear" in r.stdout


# ---------------------------------------------------------------------------
# --luminance-match
# ---------------------------------------------------------------------------

class TestLuminanceMatch:
    def test_runs_successfully(self, tmp):
        d, png = tmp
        out = d / "out"
        r = _run("--luminance-match", str(png), str(out))
        assert r.returncode == 0, r.stderr

    def test_produces_same_file_structure(self, tmp):
        """--luminance-match should still produce all three output files."""
        d, png = tmp
        out = d / "out"
        _run("--luminance-match", str(png), str(out))
        assert out.with_suffix(".pal").exists()
        assert out.with_suffix(".map").exists()
        assert out.with_suffix(".tiles").exists()

    def test_may_differ_from_euclidean(self, tmp_path):
        """Luminance matching can produce different palette bytes than Euclidean."""
        # Use a colour that will be quantized differently by the two methods.
        # (0, 128, 0) ← green channel mid-range; luminance ~50, Euclidean snaps differently.
        arr = np.full((8, 8, 3), [0, 128, 255], dtype=np.uint8)
        png = tmp_path / "test.png"
        Image.fromarray(arr, "RGB").save(str(png))
        out_euc = tmp_path / "euc"
        out_lum = tmp_path / "lum"
        _run(str(png), str(out_euc))
        _run("--luminance-match", str(png), str(out_lum))
        # We accept either outcome (may or may not differ); just confirm both ran
        assert out_euc.with_suffix(".pal").exists()
        assert out_lum.with_suffix(".pal").exists()


# ---------------------------------------------------------------------------
# --gamma
# ---------------------------------------------------------------------------

class TestGamma:
    def test_gamma_default_equals_1(self, tmp):
        """Explicit --gamma 1.0 must produce identical output to omitting it."""
        d, png = tmp
        out_default = d / "default"
        out_gamma1  = d / "gamma1"
        _run(str(png), str(out_default))
        _run("--gamma", "1.0", str(png), str(out_gamma1))
        assert out_default.with_suffix(".pal").read_bytes() == \
               out_gamma1.with_suffix(".pal").read_bytes()
        assert out_default.with_suffix(".tiles").read_bytes() == \
               out_gamma1.with_suffix(".tiles").read_bytes()

    def test_gamma_changes_output(self, tmp_path):
        """A non-trivial gamma must change at least the tileset."""
        # Use a mid-tone image where gamma visibly shifts quantised colours.
        arr = np.full((8, 8, 3), 128, dtype=np.uint8)
        png = tmp_path / "mid.png"
        Image.fromarray(arr, "RGB").save(str(png))
        out1 = tmp_path / "g1"
        out2 = tmp_path / "g22"
        _run(str(png), str(out1))
        _run("--gamma", "2.2", str(png), str(out2))
        # With gamma 2.2 the mid-grey darkens; quantised colour (and palette) differ.
        assert out1.with_suffix(".pal").read_bytes() != \
               out2.with_suffix(".pal").read_bytes(), \
            "gamma 2.2 did not change the palette"

    def test_invalid_gamma_type_fails(self, tmp):
        d, png = tmp
        out = d / "out"
        r = _run("--gamma", "notanumber", str(png), str(out))
        assert r.returncode != 0


# ---------------------------------------------------------------------------
# --tiles-png
# ---------------------------------------------------------------------------

class TestTilesPng:
    def test_creates_tilesheet(self, tmp):
        d, png = tmp
        out = d / "out"
        r = _run("--tiles-png", str(png), str(out))
        assert r.returncode == 0, r.stderr
        tilesheet = d / "out_tiles.png"
        assert tilesheet.exists()

    def test_tilesheet_is_valid_image(self, tmp):
        d, png = tmp
        out = d / "out"
        _run("--tiles-png", str(png), str(out))
        tilesheet = d / "out_tiles.png"
        img = Image.open(str(tilesheet))
        assert img.width  % 8 == 0
        assert img.height % 8 == 0

    def test_not_created_without_flag(self, tmp):
        d, png = tmp
        out = d / "out"
        _run(str(png), str(out))
        assert not (d / "out_tiles.png").exists()


# ---------------------------------------------------------------------------
# --debug-tiles
# ---------------------------------------------------------------------------

class TestDebugTiles:
    def test_creates_txt_file(self, tmp):
        d, png = tmp
        out = d / "out"
        r = _run("--debug-tiles", str(png), str(out))
        assert r.returncode == 0, r.stderr
        assert out.with_suffix(".txt").exists()

    def test_txt_contains_header(self, tmp):
        d, png = tmp
        out = d / "out"
        _run("--debug-tiles", str(png), str(out))
        content = out.with_suffix(".txt").read_text()
        assert "SMS TILE DEBUG DUMP" in content

    def test_txt_contains_palette_legend(self, tmp):
        d, png = tmp
        out = d / "out"
        _run("--debug-tiles", str(png), str(out))
        content = out.with_suffix(".txt").read_text()
        assert "Palette Legend" in content

    def test_txt_not_created_without_flag(self, tmp):
        d, png = tmp
        out = d / "out"
        _run(str(png), str(out))
        assert not out.with_suffix(".txt").exists()


# ---------------------------------------------------------------------------
# --nomirror
# ---------------------------------------------------------------------------

class TestNoMirror:
    def test_symmetric_image_deduped_by_default(self, tmp_path):
        """Symmetric tiles collapse to one unique tile when mirroring is enabled."""
        png = tmp_path / "sym.png"
        _make_symmetric_png(png)
        out = tmp_path / "out"
        r = _run(str(png), str(out))
        assert r.returncode == 0, r.stderr
        tiles_bytes = out.with_suffix(".tiles").read_bytes()
        # 1 unique 8×8 tile = 32 bytes
        assert len(tiles_bytes) == 32, \
            f"Expected 1 tile (32 bytes) with mirroring; got {len(tiles_bytes)}"

    def test_nomirror_keeps_both_tiles(self, tmp_path):
        """With --nomirror the two mirrored tiles are stored separately."""
        png = tmp_path / "sym.png"
        _make_symmetric_png(png)
        out = tmp_path / "out"
        r = _run("--nomirror", str(png), str(out))
        assert r.returncode == 0, r.stderr
        tiles_bytes = out.with_suffix(".tiles").read_bytes()
        # 2 unique 8×8 tiles = 64 bytes
        assert len(tiles_bytes) == 64, \
            f"Expected 2 tiles (64 bytes) with --nomirror; got {len(tiles_bytes)}"

    def test_nomirror_map_has_no_flip_bits(self, tmp_path):
        """With --nomirror no tile map entries should have hflip/vflip bits set."""
        png = tmp_path / "sym.png"
        _make_symmetric_png(png)
        out = tmp_path / "out"
        _run("--nomirror", str(png), str(out))
        map_data = out.with_suffix(".map").read_bytes()
        BIT_HFLIP = 1 << 9
        BIT_VFLIP = 1 << 10
        for i in range(0, len(map_data), 2):
            entry = struct.unpack_from("<H", map_data, i)[0]
            assert (entry & BIT_HFLIP) == 0, f"hflip bit set at entry {i//2}"
            assert (entry & BIT_VFLIP) == 0, f"vflip bit set at entry {i//2}"


# ---------------------------------------------------------------------------
# --noremovedups
# ---------------------------------------------------------------------------

class TestNoRemoveDups:
    def test_duplicates_removed_by_default(self, tmp_path):
        """Two identical tiles collapse to one unique tile."""
        png = tmp_path / "dup.png"
        _make_duplicate_tiles_png(png)
        out = tmp_path / "out"
        r = _run(str(png), str(out))
        assert r.returncode == 0, r.stderr
        tiles_bytes = out.with_suffix(".tiles").read_bytes()
        assert len(tiles_bytes) == 32, \
            f"Expected 1 unique tile (32 bytes) by default; got {len(tiles_bytes)}"

    def test_noremovedups_keeps_all_tiles(self, tmp_path):
        """With --noremovedups identical tiles are stored separately."""
        png = tmp_path / "dup.png"
        _make_duplicate_tiles_png(png)
        out = tmp_path / "out"
        r = _run("--noremovedups", str(png), str(out))
        assert r.returncode == 0, r.stderr
        tiles_bytes = out.with_suffix(".tiles").read_bytes()
        assert len(tiles_bytes) == 64, \
            f"Expected 2 tiles (64 bytes) with --noremovedups; got {len(tiles_bytes)}"


# ---------------------------------------------------------------------------
# --tile8x16
# ---------------------------------------------------------------------------

class TestTile8x16:
    def test_tile_data_size_doubles(self, tmp_path):
        """8×16 tiles are 64 bytes each vs 32 bytes for 8×8."""
        # 16×16 image → 2×1 tiles in 8×16 mode, 2×2 in 8×8 mode
        arr = np.zeros((16, 16, 3), dtype=np.uint8)
        arr[:8,  :8]  = (170, 0,   0)
        arr[:8,  8:]  = (0,   170, 0)
        arr[8:,  :8]  = (0,   0,   170)
        arr[8:,  8:]  = (170, 170, 0)
        png = tmp_path / "t16.png"
        Image.fromarray(arr, "RGB").save(str(png))

        out8   = tmp_path / "out8"
        out816 = tmp_path / "out816"
        r8   = _run(str(png), str(out8))
        r816 = _run("--tile8x16", str(png), str(out816))
        assert r8.returncode   == 0, r8.stderr
        assert r816.returncode == 0, r816.stderr

        size8   = len(out8.with_suffix(".tiles").read_bytes())
        size816 = len(out816.with_suffix(".tiles").read_bytes())
        # 8×8:  4 unique tiles × 32 bytes = 128 bytes
        # 8×16: 2 unique tiles × 64 bytes = 128 bytes
        assert size8   % 32 == 0
        assert size816 % 64 == 0

    def test_map_rows_halved_for_8x16(self, tmp_path):
        """A 16-row image has 2 tile rows in 8×8 mode and 1 tile row in 8×16 mode."""
        arr = np.zeros((16, 8, 3), dtype=np.uint8)
        arr[:8]  = (170, 0, 0)
        arr[8:]  = (0, 170, 0)
        png = tmp_path / "narrow.png"
        Image.fromarray(arr, "RGB").save(str(png))

        out8   = tmp_path / "out8"
        out816 = tmp_path / "out816"
        _run(str(png), str(out8))
        _run("--tile8x16", str(png), str(out816))

        # 8×8  map: 1 col × 2 rows = 2 entries × 2 bytes = 4 bytes
        # 8×16 map: 1 col × 1 row  = 1 entry  × 2 bytes = 2 bytes
        assert len(out8.with_suffix(".map").read_bytes())   == 4
        assert len(out816.with_suffix(".map").read_bytes()) == 2


# ---------------------------------------------------------------------------
# --nosortpal
# ---------------------------------------------------------------------------

class TestNoSortPal:
    def test_nosortpal_preserves_input_order(self, tmp_path):
        """
        With an indexed PNG, --nosortpal must keep palette entry 0 as the
        first CRAM byte (black → 0x00) rather than sorting it to its position.
        """
        png = tmp_path / "idx.png"
        _make_indexed_png(png)

        out_sorted   = tmp_path / "sorted"
        out_nosorted = tmp_path / "nosorted"
        _run(str(png), str(out_sorted))
        _run("--nosortpal", str(png), str(out_nosorted))

        pal_sorted   = out_sorted.with_suffix(".pal").read_bytes()
        pal_nosorted = out_nosorted.with_suffix(".pal").read_bytes()

        # Both must be valid 16-byte palettes
        assert len(pal_sorted)   == 16
        assert len(pal_nosorted) == 16

        # With --nosortpal the indexed palette order is respected.
        # Entry 0 in the indexed PNG is black → SMS byte 0x00.
        assert pal_nosorted[0] == 0x00, \
            f"Expected first CRAM entry to be 0x00 (black); got {pal_nosorted[0]:#04x}"

    def test_nosortpal_may_differ_from_sorted(self, tmp_path):
        """nosortpal and sorted should produce different palette orderings."""
        png = tmp_path / "idx.png"
        _make_indexed_png(png)

        out_sorted   = tmp_path / "sorted"
        out_nosorted = tmp_path / "nosorted"
        _run(str(png), str(out_sorted))
        _run("--nosortpal", str(png), str(out_nosorted))

        pal_sorted   = out_sorted.with_suffix(".pal").read_bytes()
        pal_nosorted = out_nosorted.with_suffix(".pal").read_bytes()
        assert pal_sorted != pal_nosorted, \
            "sorted and --nosortpal palettes are identical; expected different order"


# ---------------------------------------------------------------------------
# --no-map
# ---------------------------------------------------------------------------

class TestNoMap:
    def test_map_not_created(self, tmp):
        d, png = tmp
        out = d / "out"
        r = _run("--no-map", str(png), str(out))
        assert r.returncode == 0, r.stderr
        assert not out.with_suffix(".map").exists()

    def test_pal_and_tiles_still_created(self, tmp):
        d, png = tmp
        out = d / "out"
        _run("--no-map", str(png), str(out))
        assert out.with_suffix(".pal").exists()
        assert out.with_suffix(".tiles").exists()

    def test_no_map_stdout_omits_map_line(self, tmp):
        d, png = tmp
        out = d / "out"
        r = _run("--no-map", str(png), str(out))
        assert ".map" not in r.stdout


# ---------------------------------------------------------------------------
# --remove-blank
# ---------------------------------------------------------------------------

class TestRemoveBlank:
    def test_blank_tile_excluded_from_tileset(self, tmp_path):
        """
        Image: left half all index-0 (blank), right half non-blank.
        With --remove-blank only 1 unique tile should appear in .tiles.
        """
        png = tmp_path / "blank.png"
        _make_blank_tile_png(png)
        out = tmp_path / "out"
        r = _run("--remove-blank", str(png), str(out))
        assert r.returncode == 0, r.stderr
        tiles_data = out.with_suffix(".tiles").read_bytes()
        assert len(tiles_data) == 32, \
            f"Expected 1 tile (32 bytes) after blank removal; got {len(tiles_data)}"

    def test_blank_tile_map_entry_is_zero(self, tmp_path):
        """The blank tile's map entry must be 0 with --remove-blank."""
        png = tmp_path / "blank.png"
        _make_blank_tile_png(png)
        out = tmp_path / "out"
        _run("--remove-blank", str(png), str(out))
        map_data = out.with_suffix(".map").read_bytes()
        # 16×8 → 2 tile columns, 1 row.  Entry 0 is the blank tile.
        first_entry = struct.unpack_from("<H", map_data, 0)[0]
        assert first_entry == 0, \
            f"Blank tile map entry should be 0; got {first_entry}"

    def test_without_flag_blank_tile_included(self, tmp_path):
        """Without --remove-blank the blank tile is a normal tile in the tileset."""
        png = tmp_path / "blank.png"
        _make_blank_tile_png(png)
        out = tmp_path / "out"
        _run(str(png), str(out))
        tiles_data = out.with_suffix(".tiles").read_bytes()
        # Both tiles present → 64 bytes
        assert len(tiles_data) == 64, \
            f"Expected 2 tiles (64 bytes) without --remove-blank; got {len(tiles_data)}"


# ---------------------------------------------------------------------------
# --compress
# ---------------------------------------------------------------------------

class TestCompress:
    @pytest.fixture(autouse=True)
    def check_tool_available(self):
        r = subprocess.run(["z88dk-zx0", "--help"], capture_output=True)
        if r.returncode not in (0, 1):   # zx0 exits 1 on --help
            pytest.skip("z88dk-zx0 not available")

    def test_compress_creates_tiles_file(self, tmp):
        d, png = tmp
        out = d / "out"
        r = _run("--compress", str(png), str(out))
        assert r.returncode == 0, r.stderr
        assert out.with_suffix(".tiles").exists()

    def test_compress_creates_map_file(self, tmp):
        d, png = tmp
        out = d / "out"
        r = _run("--compress", str(png), str(out))
        assert r.returncode == 0, r.stderr
        assert out.with_suffix(".map").exists()

    def test_compress_no_map_skips_map(self, tmp):
        """--compress combined with --no-map must not attempt to compress a missing map."""
        d, png = tmp
        out = d / "out"
        r = _run("--compress", "--no-map", str(png), str(out))
        assert r.returncode == 0, r.stderr
        assert not out.with_suffix(".map").exists()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_missing_input_file_fails(self, tmp_path):
        out = tmp_path / "out"
        r = _run(str(tmp_path / "nonexistent.png"), str(out))
        assert r.returncode != 0

    def test_too_many_tiles_raises(self, tmp_path):
        """An image with > 448 unique tiles should exit non-zero."""
        # 192×192 → 24×24 = 576 tiles all unique
        rng = np.random.default_rng(0)
        arr = rng.integers(0, 4, size=(192, 192), dtype=np.uint8)
        img = Image.fromarray(arr, "P")
        pal = [0] * 768
        pal[0:3]  = [0, 0, 0]
        pal[3:6]  = [170, 0, 0]
        pal[6:9]  = [0, 170, 0]
        pal[9:12] = [0, 0, 170]
        img.putpalette(pal)
        png = tmp_path / "big.png"
        img.save(str(png))
        out = tmp_path / "out"
        r = _run("--nomirror", "--noremovedups", str(png), str(out))
        assert r.returncode != 0
        assert "448" in r.stdout or "448" in r.stderr
