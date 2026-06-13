from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
import json
import re
import struct
import wave

SND_SIGNATURE = b'ElecbyteSnd\x00'
MUGENFORGE_SND_HEADER_SIZE = 24
MUGENFORGE_SND_FIRST_OFFSET = 512

@dataclass
class SndSound:
    index: int
    riff_offset: int
    length: int
    format_tag: Optional[int] = None
    channels: Optional[int] = None
    sample_rate: Optional[int] = None
    byte_rate: Optional[int] = None
    bits_per_sample: Optional[int] = None
    group: Optional[int] = None
    sound: Optional[int] = None
    header_offset: Optional[int] = None
    warnings: List[str] = field(default_factory=list)

    @property
    def id_text(self) -> str:
        if self.group is not None and self.sound is not None:
            return f'{self.group},{self.sound}'
        return f'#{self.index}'

@dataclass
class SndInfo:
    path: Path
    has_signature: bool
    version_bytes: tuple[int, int, int, int] = (0, 0, 0, 0)
    declared_count: Optional[int] = None
    first_subfile_offset: Optional[int] = None
    sounds: List[SndSound] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def version_text(self) -> str:
        return '.'.join(str(v) for v in self.version_bytes)


def _u32(data: bytes, off: int) -> int:
    return struct.unpack_from('<I', data, off)[0]


def _i32(data: bytes, off: int) -> int:
    return struct.unpack_from('<i', data, off)[0]


def _u16(data: bytes, off: int) -> int:
    return struct.unpack_from('<H', data, off)[0]


def _parse_wave_fmt(data: bytes, start: int, end: int, sound: SndSound) -> None:
    pos = start + 12
    while pos + 8 <= end:
        chunk_id = data[pos:pos + 4]
        size = _u32(data, pos + 4)
        chunk_data = pos + 8
        chunk_end = chunk_data + size
        if chunk_end > end:
            sound.warnings.append(f'WAVE chunk {chunk_id!r} overruns RIFF length.')
            return
        if chunk_id == b'fmt ' and size >= 16:
            sound.format_tag = _u16(data, chunk_data)
            sound.channels = _u16(data, chunk_data + 2)
            sound.sample_rate = _u32(data, chunk_data + 4)
            sound.byte_rate = _u32(data, chunk_data + 8)
            sound.bits_per_sample = _u16(data, chunk_data + 14)
            return
        pos = chunk_end + (size % 2)


def _infer_legacy_ids(data: bytes, riff_offset: int) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """Best-effort SND metadata inference.

    MugenForge-built SND files use a conservative 24-byte per-sound header:
    next_offset, wav_length, group, sound, reserved, reserved. Some classic files
    use related layouts, so this checks that exact shape first and then falls back
    to nearby small-integer guesses.
    """
    off = riff_offset - MUGENFORGE_SND_HEADER_SIZE
    if off >= 0 and off + MUGENFORGE_SND_HEADER_SIZE <= len(data):
        try:
            next_offset = _u32(data, off)
            wav_len = _u32(data, off + 4)
            group = _i32(data, off + 8)
            sound = _i32(data, off + 12)
            if 0 <= group <= 99999 and 0 <= sound <= 99999 and wav_len > 0:
                # RIFF length includes 8 byte RIFF header.
                if riff_offset + wav_len <= len(data) and (next_offset == 0 or 0 < next_offset <= len(data)):
                    return group, sound, off
        except Exception:
            pass

    candidates = (20, 24, 32)
    for header_size in candidates:
        off = riff_offset - header_size
        if off < 0 or off + header_size > len(data):
            continue
        try:
            vals = [_i32(data, off + i) for i in range(0, min(header_size, 28), 4)]
        except Exception:
            continue
        # Prefer adjacent tiny values that are not the apparent length/offset fields.
        for i in range(2, max(2, len(vals) - 1)):
            g = vals[i]
            s = vals[i + 1] if i + 1 < len(vals) else None
            if isinstance(s, int) and 0 <= g <= 99999 and 0 <= s <= 99999:
                return g, s, off
    return None, None, None


def read_snd(path: Path, max_sounds: int = 20000) -> SndInfo:
    data = path.read_bytes()
    has_sig = data.startswith(SND_SIGNATURE) or data[:12].startswith(b'ElecbyteSnd')
    info = SndInfo(path=path, has_signature=has_sig)
    if has_sig and len(data) >= 32:
        info.version_bytes = tuple(data[12:16])  # type: ignore[assignment]
        try:
            info.declared_count = _u32(data, 20)
            info.first_subfile_offset = _u32(data, 24)
        except Exception:
            pass
    if len(data) < 12:
        info.warnings.append('File is too small to contain WAVE payloads.')
        return info

    pos = 0
    seen = 0
    while True:
        riff = data.find(b'RIFF', pos)
        if riff < 0 or seen >= max_sounds:
            break
        if riff + 12 > len(data):
            break
        size = _u32(data, riff + 4)
        end = riff + 8 + size
        if data[riff + 8:riff + 12] != b'WAVE':
            pos = riff + 4
            continue
        if size <= 4 or end > len(data):
            snd = SndSound(index=seen, riff_offset=riff, length=max(0, min(len(data) - riff, 8 + max(size, 0))))
            snd.warnings.append(f'Invalid RIFF length {size}.')
            info.sounds.append(snd)
            pos = riff + 4
            seen += 1
            continue
        group, sound_id, header_off = _infer_legacy_ids(data, riff)
        snd = SndSound(index=seen, riff_offset=riff, length=end - riff, group=group, sound=sound_id, header_offset=header_off)
        _parse_wave_fmt(data, riff, end, snd)
        info.sounds.append(snd)
        seen += 1
        pos = end
    if not info.sounds:
        info.warnings.append('No embedded RIFF/WAVE payloads found. This may be empty, compressed, or nonstandard.')
    if info.declared_count is not None and info.sounds and info.declared_count not in (0, len(info.sounds)):
        info.warnings.append(f'Header count hint is {info.declared_count}; RIFF scan found {len(info.sounds)} sounds.')
    return info


def export_sound(path: Path, sound: SndSound, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_id = sound.id_text.replace(',', '_').replace('#', 'idx')
    out = out_dir / f'sound_{safe_id}_off{sound.riff_offset:08X}.wav'
    data = path.read_bytes()
    out.write_bytes(data[sound.riff_offset:sound.riff_offset + sound.length])
    return out


def export_all_sounds(path: Path, out_dir: Path, max_count: Optional[int] = None) -> List[Path]:
    info = read_snd(path)
    outputs: List[Path] = []
    for sound in info.sounds[:max_count or len(info.sounds)]:
        if sound.length > 0:
            outputs.append(export_sound(path, sound, out_dir))
    return outputs


def _id_from_filename(path: Path, fallback_index: int) -> tuple[int, int]:
    stem = path.stem.lower()
    # Accept names like 5_0.wav, 5-0.wav, sound_5_0.wav, g5_s0.wav.
    nums = re.findall(r'-?\d+', stem)
    if len(nums) >= 2:
        return int(nums[-2]), int(nums[-1])
    return 0, fallback_index


def make_snd_manifest_from_wav_folder(folder: Path, out_manifest: Optional[Path] = None) -> Path:
    folder = Path(folder)
    wavs = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == '.wav')
    if not wavs:
        raise ValueError(f'No WAV files found in {folder}')
    records = []
    for idx, wav_path in enumerate(wavs):
        group, sound_id = _id_from_filename(wav_path, idx)
        fmt = {}
        try:
            with wave.open(str(wav_path), 'rb') as w:
                fmt = {
                    'channels': w.getnchannels(),
                    'sample_rate': w.getframerate(),
                    'sample_width_bytes': w.getsampwidth(),
                    'frames': w.getnframes(),
                }
        except Exception as exc:
            fmt = {'warning': f'Could not read WAV info: {exc}'}
        records.append({
            'group': group,
            'sound': sound_id,
            'filename': wav_path.name,
            'bytes': wav_path.stat().st_size,
            'format': fmt,
        })
    data = {
        'tool': 'MugenForge Studio',
        'manifest_type': 'snd_wav_manifest',
        'version': 1,
        'source_folder': str(folder),
        'sounds': records,
    }
    out = out_manifest or folder / 'mugenforge_snd_manifest.json'
    out.write_text(json.dumps(data, indent=2), encoding='utf-8')
    return out


def _load_snd_manifest(manifest_path: Path) -> list[dict]:
    data = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    records = data.get('sounds')
    if not isinstance(records, list):
        raise ValueError('Manifest does not contain a sounds list.')
    return records


def build_snd_from_manifest(manifest_path: Path, out_path: Path) -> SndInfo:
    manifest_path = Path(manifest_path)
    out_path = Path(out_path)
    records = _load_snd_manifest(manifest_path)
    if not records:
        raise ValueError('Manifest contains no sound records.')
    base_dir = manifest_path.parent
    payloads: list[tuple[dict, bytes]] = []
    for rec in records:
        filename = rec.get('filename')
        if not filename:
            raise ValueError('A sound record is missing filename.')
        wav_path = (base_dir / filename).resolve()
        if not wav_path.exists():
            raise FileNotFoundError(f'Manifest WAV not found: {wav_path}')
        blob = wav_path.read_bytes()
        if not blob.startswith(b'RIFF') or blob[8:12] != b'WAVE':
            raise ValueError(f'Not a RIFF/WAVE file: {wav_path}')
        payloads.append((rec, blob))

    header = bytearray(MUGENFORGE_SND_FIRST_OFFSET)
    header[0:12] = SND_SIGNATURE
    header[12:16] = bytes([1, 0, 1, 0])
    struct.pack_into('<I', header, 20, len(payloads))
    struct.pack_into('<I', header, 24, MUGENFORGE_SND_FIRST_OFFSET)
    header[40:64] = b'MugenForge SND v1\x00'

    chunks: list[bytes] = [bytes(header)]
    cursor = MUGENFORGE_SND_FIRST_OFFSET
    for idx, (rec, blob) in enumerate(payloads):
        next_offset = cursor + MUGENFORGE_SND_HEADER_SIZE + len(blob) if idx < len(payloads) - 1 else 0
        group = int(rec.get('group', 0))
        sound_id = int(rec.get('sound', idx))
        sub = bytearray(MUGENFORGE_SND_HEADER_SIZE)
        struct.pack_into('<I', sub, 0, next_offset)
        struct.pack_into('<I', sub, 4, len(blob))
        struct.pack_into('<i', sub, 8, group)
        struct.pack_into('<i', sub, 12, sound_id)
        struct.pack_into('<I', sub, 16, 0)
        struct.pack_into('<I', sub, 20, 0)
        chunks.append(bytes(sub))
        chunks.append(blob)
        cursor = next_offset or cursor + MUGENFORGE_SND_HEADER_SIZE + len(blob)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(b''.join(chunks))
    return read_snd(out_path)


def summarize_snd_manifest(manifest_path: Path) -> str:
    records = _load_snd_manifest(Path(manifest_path))
    lines = [f'Manifest: {manifest_path}', f'Sounds: {len(records)}']
    missing = []
    for rec in records:
        filename = rec.get('filename', '')
        if filename and not (Path(manifest_path).parent / filename).exists():
            missing.append(filename)
    if missing:
        lines.append('Missing WAV files:')
        lines.extend(f'  - {m}' for m in missing[:80])
    else:
        lines.append('All referenced WAV files are present.')
    lines.append('')
    lines.append('First sounds:')
    for rec in records[:80]:
        fmt = rec.get('format') or {}
        details = ''
        if isinstance(fmt, dict) and 'sample_rate' in fmt:
            details = f" {fmt.get('channels')}ch {fmt.get('sample_rate')}Hz {int(fmt.get('sample_width_bytes', 0))*8}bit"
        lines.append(f"  {rec.get('group', 0)},{rec.get('sound', 0)} -> {rec.get('filename', '')}{details}")
    lines.append('Build mode: simple ElecbyteSnd-compatible RIFF/WAVE payload chain for starter characters and pipeline testing.')
    return '\n'.join(lines)


def summarize_snd_detailed(path: Path) -> str:
    info = read_snd(path)
    lines = [f'File: {path.name}', f'Size: {path.stat().st_size:,} bytes']
    lines.append(f'Signature: {"ElecbyteSnd detected" if info.has_signature else "not detected"}')
    if info.has_signature:
        lines.append(f'Raw version bytes: {info.version_text}')
        if info.declared_count is not None:
            lines.append(f'Header count hint: {info.declared_count}')
        if info.first_subfile_offset is not None:
            lines.append(f'First subfile offset hint: 0x{info.first_subfile_offset:X}')
    lines.append(f'Embedded RIFF/WAVE sounds found: {len(info.sounds)}')
    if info.sounds:
        lines += ['', 'First sounds:']
        for snd in info.sounds[:80]:
            fmt = []
            if snd.channels is not None:
                fmt.append(f'{snd.channels}ch')
            if snd.sample_rate is not None:
                fmt.append(f'{snd.sample_rate}Hz')
            if snd.bits_per_sample is not None:
                fmt.append(f'{snd.bits_per_sample}bit')
            meta = ', '.join(fmt) if fmt else 'format unknown'
            lines.append(f'  #{snd.index:04d} id={snd.id_text} offset=0x{snd.riff_offset:X} bytes={snd.length:,} {meta}')
    if info.warnings:
        lines += ['', 'Warnings:']
        lines.extend(f'  - {w}' for w in info.warnings)
    return '\n'.join(lines)


def make_silent_wav(path: Path, duration_ms: int = 140, sample_rate: int = 22050, channels: int = 1, sample_width: int = 2) -> Path:
    """Create a small silent WAV placeholder for no-code sound-bank staging."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = max(1, int(sample_rate * max(1, duration_ms) / 1000))
    silence = b'\x00' * frames * max(1, channels) * max(1, sample_width)
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(max(1, channels))
        w.setsampwidth(max(1, sample_width))
        w.setframerate(max(8000, sample_rate))
        w.writeframes(silence)
    return path


def make_placeholder_sound_bank(folder: Path) -> Path:
    """Create common placeholder WAVs and a manifest for starter characters."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    names = [
        ('5_0.wav', 90),   # light hit
        ('5_1.wav', 110),  # medium hit
        ('5_2.wav', 135),  # heavy hit
        ('5_3.wav', 160),  # special/projectile
        ('5_4.wav', 170),  # uppercut/special
        ('5_6.wav', 220),  # super
        ('6_0.wav', 120),  # guard
        ('0_0.wav', 80),   # movement/step placeholder
    ]
    for name, duration in names:
        path = folder / name
        if not path.exists():
            make_silent_wav(path, duration_ms=duration)
    return make_snd_manifest_from_wav_folder(folder, folder / 'mugenforge_snd_manifest.json')
