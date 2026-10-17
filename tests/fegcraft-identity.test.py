"""Verify actual image pixels, skin UV and the complete deterministic pack."""
import importlib.util
import io
import json
from pathlib import Path
import struct
import unittest
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('identity_assets', ROOT / 'scripts/build-fegcraft-identity.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SVG = (ROOT / 'public/vector-assets/brand/vector-mark.svg').read_bytes()


def decode(data):
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    offset, compressed = 8, b''
    while offset < len(data):
        size, = struct.unpack_from('>I', data, offset)
        kind, value = data[offset + 4:offset + 8], data[offset + 8:offset + 8 + size]
        crc, = struct.unpack_from('>I', data, offset + 8 + size)
        assert crc == zlib.crc32(kind + value)
        if kind == b'IHDR':
            width, height, depth, colour, compression, filter_type, interlace = struct.unpack('>IIBBBBB', value)
            assert (depth, colour, compression, filter_type, interlace) == (8, 6, 0, 0, 0)
        elif kind == b'IDAT':
            compressed += value
        elif kind == b'IEND':
            assert offset + 12 == len(data)
        offset += 12 + size
    rows = zlib.decompress(compressed)
    assert len(rows) == height * (1 + width * 4)
    pixels = bytearray()
    for y in range(height):
        row = rows[y * (width * 4 + 1):(y + 1) * (width * 4 + 1)]
        assert row[0] == 0
        pixels.extend(row[1:])
    return width, height, pixels


class Assets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.avatar, cls.pack, cls.manifest = module.assets(SVG)

    def test_png_and_logo_geometry(self):
        width, height, pixels = decode(self.avatar)
        self.assertEqual((width, height), (256, 256))
        pixel = lambda x, y: bytes(pixels[(y * width + x) * 4:(y * width + x) * 4 + 4])
        self.assertEqual(pixel(4, 4), bytes((10, 13, 17, 255)))
        self.assertEqual(pixel(84, 128), bytes((242, 245, 247, 255)))
        self.assertEqual(pixel(160, 64), bytes((242, 245, 247, 255)))
        self.assertEqual(pixel(128, 128), bytes((10, 13, 17, 255)))

    def test_only_own_texture_and_correct_skin_uv(self):
        with zipfile.ZipFile(io.BytesIO(self.pack)) as archive:
            self.assertEqual(set(archive.namelist()), {'pack.mcmeta', 'pack.png', 'assets/vector/textures/entity/vector.png'})
            meta = json.loads(archive.read('pack.mcmeta'))['pack']
            self.assertEqual(meta['min_format'], [88, 0])
            self.assertEqual(meta['max_format'], [88, 0])
            width, height, pixels = decode(archive.read('assets/vector/textures/entity/vector.png'))
        self.assertEqual((width, height), (64, 64))
        for y in range(height):
            for x in range(width):
                alpha = pixels[(y * width + x) * 4 + 3]
                self.assertEqual(alpha, 255 if 8 <= x < 16 and 8 <= y < 16 else 0)
        self.assertLess(len(self.pack), 32768)

    def test_reproducible_and_closed_scope(self):
        self.assertEqual(module.assets(SVG), (self.avatar, self.pack, self.manifest))
        with self.assertRaisesRegex(ValueError, 'GEOMETRY_CHANGED'):
            module.assets(SVG.replace(b'M40 16', b'M39 16'))
        with self.assertRaisesRegex(ValueError, 'UNQUALIFIED_RESOURCE_FORMAT'):
            module.assets(SVG, [89, 0])


if __name__ == '__main__':
    unittest.main()
