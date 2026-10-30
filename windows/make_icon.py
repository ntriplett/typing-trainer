"""Draws windows/TypingTrainer.ico (the shortcut icon): a pixel keyboard in
the app's cozy colors. Standard library only: PNGs written by hand, packed
into an .ico (Windows reads PNG icons). Run: python windows/make_icon.py
"""

import struct
import zlib
from pathlib import Path

OUTLINE, BODY, BODY_DARK = (59, 42, 32), (122, 79, 143), (88, 56, 108)
KEY, KEY_SHADOW, GOLD, RED = (244, 230, 200), (201, 180, 143), (232, 192, 80), (224, 90, 79)


def draw() -> list[list[tuple | None]]:
    """32x32: a framed keyboard, three rows of keys and a space bar, with
    the home-row bumps (F and J) in gold and one red key."""
    g = [[None] * 32 for _ in range(32)]

    def rect(x, y, w, h, c):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                g[yy][xx] = c

    rect(1, 7, 30, 19, OUTLINE)
    rect(2, 8, 28, 17, BODY)
    rect(2, 23, 28, 2, BODY_DARK)

    def key(x, y, w, c=KEY):
        rect(x, y, w, 3, KEY_SHADOW)
        rect(x, y, w, 2, c)

    for i in range(8):
        key(4 + i * 3, 9, 2, RED if i == 7 else KEY)
    for i in range(8):
        key(5 + i * 3, 13, 2, GOLD if i in (3, 6) else KEY)
    for i in range(7):
        key(6 + i * 3, 17, 2)
    key(9, 21, 14)  # space bar
    return g


def png(grid, scale: int) -> bytes:
    size = len(grid) * scale
    rows = b""
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            c = grid[y // scale][x // scale]
            row += bytes(c + (255,)) if c else b"\0\0\0\0"
        rows += bytes(row)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    head = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", head) + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b"")


def halve(grid):
    return [row[::2] for row in grid[::2]]


def main():
    big = draw()
    images = [(256, png(big, 8)), (64, png(big, 2)), (32, png(big, 1)), (16, png(halve(big), 1))]
    out = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    for size, data in images:
        out += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    out += b"".join(data for _, data in images)
    (Path(__file__).parent / "TypingTrainer.ico").write_bytes(out)


if __name__ == "__main__":
    main()
