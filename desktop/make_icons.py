"""Generate Zebot's app icons (PNG + ICO) from pixel art, with no dependencies.

Run: python desktop/make_icons.py
"""
import struct
import zlib
from pathlib import Path

PALETTE = {
    "K": (0x0B, 0x16, 0x22, 255), "B": (0x0B, 0x6E, 0x75, 255), "L": (0x2E, 0xC4, 0xB6, 255),
    "S": (0x06, 0x11, 0x1A, 255), "W": (0xE6, 0xED, 0xF3, 255), ".": (0, 0, 0, 0),
}
# 16x16 Zebot head: antenna, CRT frame, screen with eyes and smile.
ART = [
    "......KKKK......",
    ".......LL.......",
    ".......KK.......",
    "KKKKKKKKKKKKKKKK",
    "KLLLLLLLLLLLLLLK",
    "KLBBBBBBBBBBBBBK",
    "KLBSSSSSSSSSSBBK",
    "KLBSWLSSSSWLSBBK",
    "KLBSLLSSSSLLSBBK",
    "KLBSSSSSSSSSSBBK",
    "KLBSSLSSSSLSSBBK",
    "KLBSSSLLLLSSSBBK",
    "KLBSSSSSSSSSSBBK",
    "KLBBBBBBBBBBBBBK",
    "KKKKKKKKKKKKKKKK",
    "................",
]


def png(size: int) -> bytes:
    scale = size // 16
    rows = []
    for y in range(size):
        line = ART[y // scale]
        rows.append(b"\x00" + b"".join(bytes(PALETTE[line[x // scale]]) for x in range(size)))
    raw = zlib.compress(b"".join(rows), 9)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")


def ico(sizes: list[int]) -> bytes:
    images = [png(s) for s in sizes]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, data = b"", b""
    for s, img in zip(sizes, images):
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(img), offset + len(data))
        data += img
    return header + entries + data


out = Path(__file__).parent / "src-tauri" / "icons"
out.mkdir(parents=True, exist_ok=True)
for s in (32, 128, 256):
    (out / f"{s}x{s}.png").write_bytes(png(s))
(out / "128x128@2x.png").write_bytes(png(256))
(out / "icon.png").write_bytes(png(256))
(out / "icon.ico").write_bytes(ico([16, 32, 48, 64, 256]))
print("icons:", sorted(p.name for p in out.iterdir()))
