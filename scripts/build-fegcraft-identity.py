#!/usr/bin/env python3
"""Render the existing Vector mark into public avatar/skin assets, offline."""
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import xml.etree.ElementTree as ET
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
TEXTURE = 'vector:entity/vector'
RESOURCE_FORMAT = [88, 0]


def png(width, height, pixels):
    def chunk(kind, value):
        return struct.pack('>I', len(value)) + kind + value + struct.pack('>I', zlib.crc32(kind + value))
    rows = b''.join(b'\0' + pixels[y * width * 4:(y + 1) * width * 4] for y in range(height))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows, 9)) + chunk(b'IEND', b''))


def distance(x, y, ax, ay, bx, by):
    t = max(0, min(1, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / ((bx - ax)**2 + (by - ay)**2)))
    return math.hypot(x - ax - t * (bx - ax), y - ay - t * (by - ay))


def mark(svg, size):
    # This deliberately handles just the reviewed brand path, never arbitrary SVG,
    # scripts, external references or network resources. Rounded caps/join are the
    # union of the two distance-to-segment strokes; geometry matches the source.
    root = ET.fromstring(svg)
    children = list(root)
    if (root.tag != '{http://www.w3.org/2000/svg}svg' or root.get('viewBox') != '0 0 64 64'
            or len(children) != 1 or children[0].tag != '{http://www.w3.org/2000/svg}path'
            or children[0].attrib != {'d': 'M40 16 L21 32 L40 48', 'fill': 'none', 'stroke': '#F2F5F7',
                                     'stroke-width': '6', 'stroke-linecap': 'round', 'stroke-linejoin': 'round'}):
        raise ValueError('BRAND_GEOMETRY_CHANGED_REVIEW_REQUIRED')
    pixels = bytearray()
    background, foreground = (10, 13, 17), (242, 245, 247)
    for y in range(size):
        for x in range(size):
            coverage = 0
            for sy in range(4):
                for sx in range(4):
                    px, py = (x + (sx + .5) / 4) * 64 / size, (y + (sy + .5) / 4) * 64 / size
                    coverage += min(distance(px, py, 40, 16, 21, 32), distance(px, py, 21, 32, 40, 48)) <= 3
            pixels.extend(round(b + (f - b) * coverage / 16) for b, f in zip(background, foreground))
            pixels.append(255)
    return bytes(pixels)


def assets(svg, resource_format=RESOURCE_FORMAT):
    if resource_format != RESOURCE_FORMAT:
        raise ValueError('UNQUALIFIED_RESOURCE_FORMAT')
    avatar = png(256, 256, mark(svg, 256))
    face = mark(svg, 8)
    # Vanilla skin UV: front of the head occupies x=8..15, y=8..15.
    # No hat layer, player UUID, texture-service upload or real account needed.
    skin = bytearray(64 * 64 * 4)
    for y in range(8):
        start = ((y + 8) * 64 + 8) * 4
        skin[start:start + 32] = face[y * 32:(y + 1) * 32]
    texture = png(64, 64, bytes(skin))
    meta = {'pack': {'description': 'Vector chat logo for FEGCraft', 'min_format': resource_format, 'max_format': resource_format}}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted({'pack.mcmeta': json.dumps(meta, separators=(',', ':')).encode(),
                                    'pack.png': avatar, 'assets/vector/textures/entity/vector.png': texture}.items()):
            info = zipfile.ZipInfo(name, (2026, 10, 17, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, content)
    pack = stream.getvalue()
    manifest = {'scope': 'vector-chat-identity-only', 'minecraft_version': '26.2', 'resource_format': resource_format,
                'logo_texture': TEXTURE, 'avatar_sha256': hashlib.sha256(avatar).hexdigest(),
                'pack_sha256': hashlib.sha256(pack).hexdigest(), 'pack_sha1': hashlib.sha1(pack).hexdigest(),
                'source_svg_sha256': hashlib.sha256(svg).hexdigest(), 'pack_bytes': len(pack),
                'avatar_bytes': len(avatar), 'contains_vanilla_overrides': False}
    return avatar, pack, manifest


def write(output):
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    avatar, pack, manifest = assets((ROOT / 'public/vector-assets/brand/vector-mark.svg').read_bytes())
    (output / 'vector-avatar.png').write_bytes(avatar)
    (output / 'vector-chat-26-2.zip').write_bytes(pack)
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    print(json.dumps(write(parser.parse_args().output), indent=2))
