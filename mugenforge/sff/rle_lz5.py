from __future__ import annotations

import struct
import zlib


def _u32(data: bytes, off: int) -> int:
    return struct.unpack_from('<I', data, off)[0]


def _mf_strip_size_prefix(blob: bytes, expected: int) -> bytes:
    if len(blob) >= 4:
        declared = _u32(blob, 0)
        if declared == expected or declared == len(blob) - 4:
            return blob[4:]
    return blob


def decode_sff2_rle8_indices(payload: bytes, expected_pixels: int) -> bytes:
    if len(payload) < 4:
        raise ValueError('RLE8 payload is shorter than its uncompressed-size prefix.')
    declared = struct.unpack_from('<I', payload, 0)[0]
    out = bytearray()
    run_len: int | None = None
    for b in payload[4:]:
        if ((b & 0xC0) != 0x40) or run_len is not None:
            n = 1 if run_len is None else run_len
            if n > 0:
                out.extend(bytes([b]) * n)
            run_len = None
            if expected_pixels and len(out) >= expected_pixels:
                break
        else:
            run_len = b - 0x40
    if expected_pixels:
        if len(out) < expected_pixels:
            out.extend(b'\x00' * (expected_pixels - len(out)))
        elif len(out) > expected_pixels:
            del out[expected_pixels:]
    return bytes(out)


def encode_sff2_rle8_indices(indices: bytes) -> bytes:
    data = bytes(indices)
    out = bytearray(struct.pack('<I', len(data)))
    i = 0
    n = len(data)
    while i < n:
        value = data[i]
        run = 1
        while i + run < n and data[i + run] == value and run < 63:
            run += 1
        if run >= 2:
            out.append(0x40 + run)
            out.append(value)
            i += run
            continue
        if 0x40 <= value <= 0x7F:
            out.append(0x41)
            out.append(value)
        else:
            out.append(value)
        i += 1
    return bytes(out)


def _unpack_5bit_indices(payload: bytes, expected_pixels: int) -> bytes:
    out = bytearray()
    acc = 0
    bits = 0
    for b in payload:
        acc |= int(b) << bits
        bits += 8
        while bits >= 5 and (not expected_pixels or len(out) < expected_pixels):
            out.append(acc & 0x1F)
            acc >>= 5
            bits -= 5
        if expected_pixels and len(out) >= expected_pixels:
            break
    if expected_pixels and len(out) < expected_pixels:
        out.extend(b'\x00' * (expected_pixels - len(out)))
    return bytes(out[:expected_pixels] if expected_pixels else out)


def _mf_decode_rle_pairs(comp: bytes, expected: int, max_value: int = 255) -> bytes:
    out = bytearray()
    pos = 0
    while pos + 1 < len(comp) and len(out) < expected:
        run = comp[pos]
        val = comp[pos + 1] & max_value
        pos += 2
        if run == 0:
            if pos < len(comp):
                lit_count = min(comp[pos], max(0, len(comp) - pos - 1))
                pos += 1
                out.extend(comp[pos:pos + lit_count])
                pos += lit_count
            continue
        out.extend([val] * run)
    return bytes(out[:expected])


def _mf_encode_rle_pairs(raw: bytes, max_value: int = 255) -> bytes:
    if not raw:
        return b''
    out = bytearray()
    i = 0
    n = len(raw)
    while i < n:
        value = raw[i] & max_value
        run = 1
        while i + run < n and run < 255 and (raw[i + run] & max_value) == value:
            run += 1
        out.extend((run, value))
        i += run
    return bytes(out)


def _mf_decode_lz5_stream(comp: bytes, expected: int) -> bytes:
    out = bytearray()
    pos = 0
    while pos < len(comp) and len(out) < expected:
        flags = comp[pos]
        pos += 1
        for bit in range(8):
            if len(out) >= expected or pos >= len(comp):
                break
            if flags & (1 << bit):
                out.append(comp[pos])
                pos += 1
            else:
                if pos + 1 >= len(comp):
                    break
                b1 = comp[pos]
                b2 = comp[pos + 1]
                pos += 2
                distance = ((b2 & 0xF0) << 4) | b1
                length = (b2 & 0x0F) + 3
                distance += 1
                if distance <= 0 or distance > len(out):
                    out.extend(b'\x00' * length)
                else:
                    for _ in range(length):
                        out.append(out[-distance])
                        if len(out) >= expected:
                            break
    return bytes(out[:expected])


def _mf_encode_lz5_literal(raw: bytes) -> bytes:
    out = bytearray()
    pos = 0
    while pos < len(raw):
        chunk = raw[pos:pos + 8]
        out.append((1 << len(chunk)) - 1)
        out.extend(chunk)
        pos += len(chunk)
    return bytes(out)


def _mf_decode_ele_rle8(comp: bytes, expected: int) -> bytes:
    comp = _mf_strip_size_prefix(comp, expected)
    out = bytearray()
    pos = 0
    while pos < len(comp) and len(out) < expected:
        b = comp[pos]
        pos += 1
        if (b & 0xC0) == 0x40:
            run = b & 0x3F
            if pos >= len(comp):
                break
            val = comp[pos]
            pos += 1
            out.extend([val] * run)
        else:
            out.append(b)
    if len(out) != expected:
        pair = _mf_decode_rle_pairs(_mf_strip_size_prefix(comp, expected), expected, 255)
        if len(pair) == expected:
            return pair
        raise ValueError(f'RLE8 decoded {len(out)} bytes, expected {expected}.')
    return bytes(out)


def _mf_encode_ele_rle8(raw: bytes) -> bytes:
    out = bytearray()
    i = 0
    n = len(raw)
    while i < n:
        val = raw[i]
        run = 1
        while i + run < n and raw[i + run] == val and run < 63:
            run += 1
        if run > 1 or (val & 0xC0) == 0x40:
            out.append(0x40 | run)
            out.append(val)
        else:
            out.append(val)
        i += run
    return bytes(out)


def _mf_decode_ele_rle5(comp: bytes, expected: int) -> bytes:
    comp0 = _mf_strip_size_prefix(comp, expected)
    out = bytearray(expected)
    pos = 0
    j = 0
    try:
        while j < expected and pos < len(comp0):
            rl = comp0[pos]
            pos += 1
            if pos >= len(comp0):
                break
            token = comp0[pos]
            pos += 1
            dl = token & 0x7F
            c = 0
            if token & 0x80:
                if pos >= len(comp0):
                    break
                c = comp0[pos] & 0x1F
                pos += 1
            while True:
                if j < expected:
                    out[j] = c & 0x1F
                    j += 1
                rl -= 1
                if rl < 0:
                    dl -= 1
                    if dl < 0:
                        break
                    if pos >= len(comp0):
                        raise ValueError('RLE5 stream ended inside a delta run.')
                    t = comp0[pos]
                    pos += 1
                    c = t & 0x1F
                    rl = t >> 5
        if j == expected:
            return bytes(out)
    except Exception:
        pass
    try:
        pair = _mf_decode_rle_pairs(comp0, expected, 31)
        if len(pair) == expected:
            return pair
    except Exception:
        pass
    unpacked = _mf_unpack_5bit_for_v551(comp0, expected)
    if len(unpacked) == expected:
        return unpacked
    raise ValueError(f'RLE5 decoded {j} bytes, expected {expected}.')


def _mf_encode_ele_rle5(raw5: bytes) -> bytes:
    raw5 = bytes((b & 0x1F) for b in raw5)
    out = bytearray()
    pos = 0
    while pos < len(raw5):
        chunk = raw5[pos:pos + 128]
        if not chunk:
            break
        out.append(0)
        out.append(0x80 | (len(chunk) - 1))
        out.append(chunk[0])
        for b in chunk[1:]:
            out.append(b & 0x1F)
        pos += len(chunk)
    return bytes(out)


def _mf_unpack_5bit_for_v551(data: bytes, expected: int) -> bytes:
    out = bytearray()
    bitbuf = 0
    bitcount = 0
    for b in data:
        bitbuf |= int(b) << bitcount
        bitcount += 8
        while bitcount >= 5 and len(out) < expected:
            out.append(bitbuf & 0x1F)
            bitbuf >>= 5
            bitcount -= 5
        if len(out) >= expected:
            break
    return bytes(out)


def _mf_decode_ele_lz5(comp: bytes, expected: int) -> bytes:
    comp0 = _mf_strip_size_prefix(comp, expected)
    out = bytearray(expected)
    pos = 0
    j = 0
    try:
        if not comp0:
            raise ValueError('empty LZ5 stream')
        ctl = comp0[pos]
        pos += 1
        cts = 0
        rb = 0
        rbc = 0
        while j < expected and pos < len(comp0):
            d = comp0[pos]
            pos += 1
            if ctl & (1 << cts):
                rb |= (d & 0xC0) >> rbc
                rbc += 2
                n = d & 0x3F
                if rbc < 8:
                    if pos >= len(comp0):
                        break
                    dist = comp0[pos] + 1
                    pos += 1
                else:
                    dist = rb + 1
                    rb = 0
                    rbc = 0
                if dist <= 0 or dist > j:
                    raise ValueError('invalid LZ5 back-reference distance')
                for _ in range(n + 1):
                    if j >= expected:
                        break
                    out[j] = out[j - dist]
                    j += 1
            else:
                if d & 0xE0 == 0:
                    val = d & 0x1F
                    if pos >= len(comp0):
                        break
                    n = comp0[pos] + 8
                    pos += 1
                else:
                    n = d >> 5
                    val = d & 0x1F
                for _ in range(n):
                    if j >= expected:
                        break
                    out[j] = val
                    j += 1
            cts += 1
            if cts >= 8:
                cts = 0
                if pos >= len(comp0):
                    break
                ctl = comp0[pos]
                pos += 1
        if j == expected:
            return bytes(out)
    except Exception:
        pass
    try:
        old = _mf_decode_lz5_stream(comp0, expected)
        if len(old) == expected:
            return old
    except Exception:
        pass
    unpacked = _mf_unpack_5bit_for_v551(comp0, expected)
    if len(unpacked) == expected:
        return unpacked
    raise ValueError(f'LZ5 decoded {j} bytes, expected {expected}.')


def _mf_encode_ele_lz5_literal(raw5: bytes) -> bytes:
    raw5 = bytes((b & 0x1F) for b in raw5)
    out = bytearray()
    pos = 0
    while pos < len(raw5):
        control_pos = len(out)
        out.append(0)
        tokens = 0
        while tokens < 8 and pos < len(raw5):
            value = raw5[pos] & 0x1F
            run = 1
            while pos + run < len(raw5) and run < 263 and (raw5[pos + run] & 0x1F) == value:
                run += 1
            if run <= 7:
                out.append((run << 5) | value)
            else:
                out.append(value)
                out.append(run - 8)
            pos += run
            tokens += 1
        out[control_pos] = 0
    return bytes(out)
