"""Read dimensions from PNG, JPEG, and WebP headers without decoding pixels."""

import struct


def dimensions(raw):
    if (
        raw.startswith(b"\x89PNG\r\n\x1a\n")
        and raw[12:16] == b"IHDR"
        and len(raw) >= 24
    ):
        width, height = struct.unpack(">II", raw[16:24])
    elif raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        variant = raw[12:16]
        if variant == b"VP8X" and len(raw) >= 30:
            width = int.from_bytes(raw[24:27], "little") + 1
            height = int.from_bytes(raw[27:30], "little") + 1
        elif variant == b"VP8L" and raw[20:21] == b"\x2f" and len(raw) >= 25:
            bits = int.from_bytes(raw[21:25], "little")
            width, height = (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        elif variant == b"VP8 " and raw[23:26] == b"\x9d\x01\x2a" and len(raw) >= 30:
            width, height = (n & 0x3FFF for n in struct.unpack("<HH", raw[26:30]))
        else:
            raise ValueError("无法解析 WebP 尺寸")
    elif raw.startswith(b"\xff\xd8"):
        pos = 2
        while pos + 4 <= len(raw) and raw[pos] == 255:
            while pos < len(raw) and raw[pos] == 255:
                pos += 1
            if pos + 2 >= len(raw):
                break
            marker = raw[pos]
            length = int.from_bytes(raw[pos + 1 : pos + 3], "big")
            if length < 2 or pos + 1 + length > len(raw):
                break
            if (
                marker
                in (192, 193, 194, 195, 197, 198, 199, 201, 202, 203, 205, 206, 207)
                and length >= 7
            ):
                height, width = struct.unpack(">HH", raw[pos + 4 : pos + 8])
                break
            pos += length + 1
        else:
            raise ValueError("无法解析 JPEG 尺寸")
        if "width" not in locals():
            raise ValueError("无法解析 JPEG 尺寸")
    else:
        raise ValueError("无法读取图片尺寸")
    if not (
        0 < width <= 16000 and 0 < height <= 16000 and width * height <= 52_000_000
    ):
        raise ValueError("图片尺寸过大或无效")
    return [width, height]
