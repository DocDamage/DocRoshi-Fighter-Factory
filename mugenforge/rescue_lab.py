from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import json
import re
import struct
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .parsers import parse_air, read_text_safely, write_text_safely
from .sff_codec import build_sff_v1_from_manifest, summarize_manifest_for_sff

RESCUE_LAB_VERSION = "3.2"

IMAGE_EXTS = {".png", ".pcx", ".bmp", ".gif", ".jpg", ".jpeg", ".webp"}
BINARY_EXTS = {".sff", ".snd", ".bin", ".dat"}


@dataclass
class RescueAsset:
    kind: str
    source: str
    offset: int
    size: int
    path: str
    note: str = ""


@dataclass
class RescueResult:
    title: str = "Rescue Lab Result"
    created_files: List[str] = field(default_factory=list)
    changed_files: List[str] = field(default_factory=list)
    skipped_files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def merge(self, other: object, prefix: str = "") -> None:
        p = f"{prefix}: " if prefix else ""
        for attr in ("created_files", "changed_files", "skipped_files", "warnings", "notes"):
            vals = getattr(other, attr, []) or []
            getattr(self, attr).extend([p + str(v) for v in vals])

    def to_text(self) -> str:
        lines = [self.title, "=" * len(self.title), ""]
        for label, values in [
            ("Notes", self.notes),
            ("Created", self.created_files),
            ("Changed", self.changed_files),
            ("Skipped", self.skipped_files),
            ("Warnings", self.warnings),
        ]:
            if values:
                lines.append(label + ":")
                lines.extend(f"- {v}" for v in values)
                lines.append("")
        if len(lines) <= 3:
            lines.append("No output was created.")
        return "\n".join(lines).rstrip() + "\n"


def _rel(root: Path, path: Path | str | None) -> str:
    if path is None:
        return "missing"
    try:
        return str(Path(path).relative_to(root)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _now() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _discover_main_files(root: Path) -> Dict[str, Optional[Path]]:
    root = Path(root)
    out: Dict[str, Optional[Path]] = {"root": root}
    for ext in ("def", "cmd", "cns", "air", "sff", "snd"):
        hits = sorted(root.glob(f"*.{ext}"), key=lambda p: p.name.lower())
        out[ext] = hits[0] if hits else None
    # A few chars keep CNS in states/ or data/.
    if out.get("air") is None:
        hits = sorted(root.rglob("*.air"), key=lambda p: str(p).lower())
        out["air"] = hits[0] if hits else None
    if out.get("sff") is None:
        hits = sorted(root.rglob("*.sff"), key=lambda p: str(p).lower())
        out["sff"] = hits[0] if hits else None
    if out.get("snd") is None:
        hits = sorted(root.rglob("*.snd"), key=lambda p: str(p).lower())
        out["snd"] = hits[0] if hits else None
    return out


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_safely(path, text)


def _find_pngs(data: bytes) -> Iterable[Tuple[int, int, bytes, str]]:
    sig = b"\x89PNG\r\n\x1a\n"
    pos = 0
    while True:
        start = data.find(sig, pos)
        if start < 0:
            break
        iend = data.find(b"IEND", start + 8)
        if iend < 0:
            yield start, 0, b"", "PNG signature found but IEND chunk was not found."
            pos = start + 8
            continue
        end = iend + 8  # type + CRC, while length bytes already sit before IEND
        if end <= len(data):
            yield start, end - start, data[start:end], "embedded PNG"
        pos = max(end, start + 8)


def _find_wavs(data: bytes) -> Iterable[Tuple[int, int, bytes, str]]:
    pos = 0
    while True:
        start = data.find(b"RIFF", pos)
        if start < 0:
            break
        if start + 12 <= len(data) and data[start + 8:start + 12] == b"WAVE":
            size = struct.unpack_from("<I", data, start + 4)[0] + 8
            if 12 <= size <= len(data) - start:
                yield start, size, data[start:start + size], "embedded RIFF/WAVE"
                pos = start + size
                continue
        pos = start + 4


def _pcx_candidate_offsets(data: bytes) -> List[int]:
    # PCX: manufacturer 0x0A, version usually 0/2/3/5, encoding 1, bpp commonly 1/2/4/8.
    pat = re.compile(rb"\x0a[\x00\x02\x03\x05]\x01[\x01\x02\x04\x08]")
    return [m.start() for m in pat.finditer(data)]


def _find_pcxs(data: bytes) -> Iterable[Tuple[int, int, bytes, str]]:
    offsets = _pcx_candidate_offsets(data)
    if not offsets:
        return
    boundaries = sorted(set(offsets + [m[0] for m in _find_pngs(data)] + [m[0] for m in _find_wavs(data)] + [len(data)]))
    for start in offsets:
        nexts = [b for b in boundaries if b > start]
        bound = nexts[0] if nexts else len(data)
        search_start = min(start + 128, len(data))
        # 8-bit PCX usually ends with palette marker 0x0C + 768-byte palette.
        marker = data.rfind(b"\x0c", search_start, max(search_start, bound - 768))
        if marker >= 0 and marker + 769 <= bound:
            end = marker + 769
            size = end - start
            if 128 <= size <= 10_000_000:
                yield start, size, data[start:end], "embedded PCX with 256-color palette marker"


def scan_binary_for_embedded_assets(binary_path: Path, out_dir: Path) -> List[RescueAsset]:
    binary_path = Path(binary_path)
    out_dir = Path(out_dir)
    data = binary_path.read_bytes()
    assets: List[RescueAsset] = []
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", binary_path.stem)

    def save(kind: str, ext: str, offset: int, size: int, payload: bytes, note: str) -> None:
        sub = out_dir / kind.lower()
        sub.mkdir(parents=True, exist_ok=True)
        index = len([a for a in assets if a.kind == kind])
        path = sub / f"{safe_stem}_{kind.lower()}_{index:04d}_off_{offset:08x}.{ext}"
        path.write_bytes(payload)
        assets.append(RescueAsset(kind=kind, source=str(binary_path), offset=offset, size=size, path=str(path), note=note))

    for offset, size, payload, note in _find_pngs(data):
        if payload:
            save("PNG", "png", offset, size, payload, note)
    for offset, size, payload, note in _find_pcxs(data):
        save("PCX", "pcx", offset, size, payload, note)
    for offset, size, payload, note in _find_wavs(data):
        save("WAV", "wav", offset, size, payload, note)
    return assets


def scan_project_embedded_assets(root: Path) -> RescueResult:
    root = Path(root)
    result = RescueResult("Embedded Asset Scan")
    out_dir = root / "rescue_lab" / "embedded_assets"
    assets: List[RescueAsset] = []
    files = [p for p in sorted(root.rglob("*"), key=lambda p: str(p).lower()) if p.is_file() and p.suffix.lower() in {".sff", ".snd"}]
    if not files:
        result.warnings.append("No .sff or .snd files found to scan.")
    for p in files:
        try:
            found = scan_binary_for_embedded_assets(p, out_dir)
            assets.extend(found)
            result.notes.append(f"{_rel(root, p)}: {len(found)} embedded asset candidates found.")
        except Exception as exc:
            result.warnings.append(f"Failed to scan {_rel(root, p)}: {exc}")
    payload = {
        "version": RESCUE_LAB_VERSION,
        "root": str(root),
        "generated_at": _now(),
        "assets": [asset.__dict__ for asset in assets],
    }
    manifest = root / "rescue_lab" / "EMBEDDED_ASSET_SCAN.json"
    _write_json(manifest, payload)
    report = root / "rescue_lab" / "EMBEDDED_ASSET_SCAN.md"
    lines = ["# Embedded Asset Scan", "", f"Generated: {_now()}", "", f"Candidates: {len(assets)}", ""]
    for asset in assets[:500]:
        lines.append(f"- `{asset.kind}` from `{_rel(root, asset.source)}` at `0x{asset.offset:08X}` size `{asset.size}` → `{_rel(root, asset.path)}`")
    if len(assets) > 500:
        lines.append(f"- ... {len(assets) - 500} more entries in JSON")
    lines += ["", "## Notes", "", "This is a best-effort rescue scan. It is useful for unknown or unsupported packed files, but it does not replace full SFF v2 table parsing."]
    _write_text(report, "\n".join(lines) + "\n")
    result.created_files += [_rel(root, manifest), _rel(root, report)]
    if assets:
        result.created_files.append(_rel(root, out_dir))
    return result


def _load_embedded_manifest(root: Path) -> List[Dict[str, object]]:
    manifest = Path(root) / "rescue_lab" / "EMBEDDED_ASSET_SCAN.json"
    if not manifest.exists():
        return []
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        return list(data.get("assets") or [])
    except Exception:
        return []


def _air_unique_sprite_refs(root: Path) -> List[Tuple[int, int]]:
    files = _discover_main_files(root)
    air = files.get("air")
    if not air or not air.exists():
        return []
    seen: set[Tuple[int, int]] = set()
    refs: List[Tuple[int, int]] = []
    for action in parse_air(read_text_safely(air)):
        for frame in action.frames:
            key = (int(frame.group), int(frame.image))
            if key not in seen:
                seen.add(key)
                refs.append(key)
    return refs


def build_recovery_manifest_from_air(root: Path) -> RescueResult:
    root = Path(root)
    result = RescueResult("Recovery Manifest From AIR")
    assets = _load_embedded_manifest(root)
    if not assets:
        scan = scan_project_embedded_assets(root)
        result.merge(scan, "scan")
        assets = _load_embedded_manifest(root)
    image_assets = [a for a in assets if str(a.get("kind", "")).upper() in {"PNG", "PCX"}]
    refs = _air_unique_sprite_refs(root)
    if not image_assets:
        result.warnings.append("No extracted PNG/PCX assets are available. Run the embedded scan or use v1 SFF export first.")
    if not refs:
        result.warnings.append("No AIR sprite references found. Manifest will use sequential group 9000 image IDs.")
    records = []
    for i, asset in enumerate(image_assets):
        if i < len(refs):
            group, image = refs[i]
        else:
            group, image = 9000 + (i // 1000), i % 1000
        source_path = Path(str(asset.get("path", "")))
        records.append({
            "group": int(group),
            "image": int(image),
            "axis": {"x": 0, "y": 0},
            "filename": str(source_path.relative_to(root / "rescue_lab") if source_path.is_absolute() and str(source_path).startswith(str(root / "rescue_lab")) else source_path),
            "source_offset": int(asset.get("offset", 0) or 0),
            "source_kind": str(asset.get("kind", "image")),
        })
    out = root / "rescue_lab" / "recovered_sprite_manifest.json"
    # Build manifest paths relative to the manifest file itself.
    normalized = []
    for rec in records:
        fn = Path(str(rec["filename"]))
        if fn.is_absolute():
            try:
                rec["filename"] = str(fn.relative_to(out.parent)).replace("\\", "/")
            except Exception:
                rec["filename"] = str(fn)
        normalized.append(rec)
    _write_json(out, {"version": RESCUE_LAB_VERSION, "sprites": normalized})
    result.created_files.append(_rel(root, out))
    result.notes.append(f"Mapped {len(normalized)} extracted image candidates to {len(refs)} AIR sprite references.")
    if len(image_assets) > len(refs) and refs:
        result.warnings.append("There are more extracted images than AIR references. Extra images were placed in group 9000+.")
    if len(refs) > len(image_assets):
        result.warnings.append("There are more AIR references than extracted images. Some sprites still need replacement art.")
    return result


def build_recovered_sff_v1(root: Path, out_name: str = "recovered_from_rescue.sff") -> RescueResult:
    root = Path(root)
    result = RescueResult("Build Recovered SFF v1")
    manifest = root / "rescue_lab" / "recovered_sprite_manifest.json"
    if not manifest.exists():
        make = build_recovery_manifest_from_air(root)
        result.merge(make, "manifest")
    if not manifest.exists():
        result.warnings.append("Recovery manifest could not be created.")
        return result
    out_path = root / out_name
    try:
        build_sff_v1_from_manifest(manifest, out_path)
        result.created_files.append(_rel(root, out_path))
        summary = root / "rescue_lab" / "RECOVERED_SFF_BUILD_SUMMARY.md"
        _write_text(summary, "# Recovered SFF v1 Build\n\n" + summarize_manifest_for_sff(manifest) + "\n")
        result.created_files.append(_rel(root, summary))
    except Exception as exc:
        result.warnings.append(f"Build failed: {exc}")
    return result


def create_rescue_contact_sheet(root: Path, max_images: int = 160) -> RescueResult:
    root = Path(root)
    result = RescueResult("Rescue Contact Sheet")
    assets = _load_embedded_manifest(root)
    if not assets:
        scan = scan_project_embedded_assets(root)
        result.merge(scan, "scan")
        assets = _load_embedded_manifest(root)
    image_paths = [Path(str(a.get("path"))) for a in assets if str(a.get("kind", "")).upper() in {"PNG", "PCX"}]
    image_paths = [p for p in image_paths if p.exists()][:max_images]
    if not image_paths:
        result.warnings.append("No extracted image files found for contact sheet.")
        return result
    try:
        from PIL import Image, ImageDraw
    except Exception:
        result.warnings.append("Pillow is required for contact sheets. Install with: pip install Pillow")
        return result
    cell_w, cell_h = 160, 190
    cols = 5
    rows = (len(image_paths) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), "white")
    draw = ImageDraw.Draw(sheet)
    for idx, path in enumerate(image_paths):
        try:
            img = Image.open(path).convert("RGBA")
            img.thumbnail((140, 140))
            x = (idx % cols) * cell_w + (cell_w - img.width) // 2
            y = (idx // cols) * cell_h + 8
            bg = Image.new("RGBA", img.size, "white")
            bg.alpha_composite(img)
            sheet.paste(bg.convert("RGB"), (x, y))
            label = path.name[:24]
            draw.text(((idx % cols) * cell_w + 8, (idx // cols) * cell_h + 152), label, fill=(0, 0, 0))
        except Exception as exc:
            draw.text(((idx % cols) * cell_w + 8, (idx // cols) * cell_h + 8), f"ERR {path.name}\n{exc}"[:80], fill=(0, 0, 0))
    out = root / "rescue_lab" / "RECOVERY_CONTACT_SHEET.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    result.created_files.append(_rel(root, out))
    result.notes.append(f"Contact sheet includes {len(image_paths)} extracted image candidates.")
    return result


def write_beginner_rescue_plan(root: Path) -> RescueResult:
    root = Path(root)
    result = RescueResult("Beginner Rescue Plan")
    files = _discover_main_files(root)
    assets = _load_embedded_manifest(root)
    refs = _air_unique_sprite_refs(root)
    pngs = sum(1 for a in assets if str(a.get("kind", "")).upper() == "PNG")
    pcxs = sum(1 for a in assets if str(a.get("kind", "")).upper() == "PCX")
    wavs = sum(1 for a in assets if str(a.get("kind", "")).upper() == "WAV")
    lines = [
        "# MugenForge Rescue Lab: Beginner Plan",
        "",
        "This file explains the safest recovery path when a project has packed assets, missing source folders, unsupported SFF/SND layouts, or confusing AIR references.",
        "",
        "## Current project signals",
        "",
        f"- AIR file: `{_rel(root, files.get('air')) if files.get('air') else 'missing'}`",
        f"- SFF file: `{_rel(root, files.get('sff')) if files.get('sff') else 'missing'}`",
        f"- SND file: `{_rel(root, files.get('snd')) if files.get('snd') else 'missing'}`",
        f"- Unique AIR sprite refs: `{len(refs)}`",
        f"- Extracted PNG candidates: `{pngs}`",
        f"- Extracted PCX candidates: `{pcxs}`",
        f"- Extracted WAV candidates: `{wavs}`",
        "",
        "## Safest workflow",
        "",
        "1. Run **Scan Embedded Assets** first.",
        "2. Open `rescue_lab/RECOVERY_CONTACT_SHEET.png` to see what the scanner found.",
        "3. Run **Build Recovery Manifest From AIR** so extracted sprites are mapped to AIR group/image IDs when possible.",
        "4. Edit/replace images in the extracted asset folders if needed.",
        "5. Run **Build Recovered SFF v1** only when you want a fresh starter SFF, not a byte-perfect original file.",
        "6. Use Animation Player and CLSN Editor to fix timing, axes, and hitboxes visually.",
        "",
        "## Important limitation",
        "",
        "Rescue Lab does not claim full SFF v2 rebuild support. It is a practical asset-recovery lane for creators who need to keep working without writing code or reverse-editing binary tables by hand.",
    ]
    out = root / "rescue_lab" / "BEGINNER_RESCUE_PLAN.md"
    _write_text(out, "\n".join(lines) + "\n")
    result.created_files.append(_rel(root, out))
    return result


def run_rescue_lab_pass(root: Path) -> RescueResult:
    root = Path(root)
    result = RescueResult("One-Click Rescue Lab Pass")
    for label, func in [
        ("scan", scan_project_embedded_assets),
        ("manifest", build_recovery_manifest_from_air),
        ("contact", create_rescue_contact_sheet),
        ("plan", write_beginner_rescue_plan),
    ]:
        try:
            result.merge(func(root), label)
        except Exception as exc:
            result.warnings.append(f"{label} failed: {exc}")
    result.notes.append("One-click rescue finished. Review rescue_lab/BEGINNER_RESCUE_PLAN.md before replacing packed assets.")
    return result
