from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import csv
import json
import math
import os
import re
import shutil
import zipfile
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .parsers import COMMON_ANIMS, parse_air, parse_code, parse_def, read_text_safely, scan_project, write_text_safely
from .sff_codec import read_sff, sprite_lookup, export_all_sprites, build_sff_v1_from_manifest
from .snd_codec import read_snd, make_placeholder_sound_bank, build_snd_from_manifest
from .automation_bank import apply_kit, feature_bank_stats_text, auto_setup_project
from . import factory_plus as fp

FACTORY_MAX_VERSION = "2.5.0"

IMAGE_SUFFIXES = {".png", ".pcx", ".bmp", ".gif", ".jpg", ".jpeg", ".webp"}
TEXT_SUFFIXES = {".def", ".air", ".cmd", ".cns", ".st", ".txt", ".md", ".json", ".ini", ".cfg"}


@dataclass
class MaxResult:
    title: str = "Factory Max Result"
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
        for label, attr in [
            ("Notes", self.notes),
            ("Created", self.created_files),
            ("Changed", self.changed_files),
            ("Skipped", self.skipped_files),
            ("Warnings", self.warnings),
        ]:
            if attr:
                lines.append(label + ":")
                lines.extend(f"- {item}" for item in attr)
                lines.append("")
        if len(lines) <= 3:
            lines.append("No changes made.")
        return "\n".join(lines).rstrip() + "\n"


def _now() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _rel(root: Path, path: Path | str) -> str:
    try:
        return str(Path(path).relative_to(root)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _backup(path: Path) -> Optional[Path]:
    if not path.exists():
        return None
    backup = path.with_name(path.name + f".bak_{_now()}")
    backup.write_bytes(path.read_bytes())
    return backup


def _write(path: Path, text: str, result: Optional[MaxResult] = None, root: Optional[Path] = None, changed: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and changed:
        _backup(path)
    write_text_safely(path, text)
    if result is not None:
        target = _rel(root or path.parent, path)
        (result.changed_files if changed else result.created_files).append(target)
    return path


def _discover_files(root: Path) -> Dict[str, Optional[Path]]:
    root = Path(root)
    out: Dict[str, Optional[Path]] = {"root": root}
    def_path = root / f"{root.name}.def"
    if not def_path.exists():
        defs = sorted(root.glob("*.def"), key=lambda p: p.name.lower())
        def_path = defs[0] if defs else def_path
    out["def"] = def_path if def_path.exists() else None
    refs: Dict[str, str] = {}
    if out["def"]:
        try:
            sec = parse_def(read_text_safely(out["def"]))
            files = sec.get("files")
            if files:
                refs = {k.lower(): v.strip().strip('"') for k, v in files.values.items()}
        except Exception:
            refs = {}
    def from_ref(key: str, ext: str) -> Optional[Path]:
        ref = refs.get(key)
        if ref:
            p = (root / ref).resolve()
            if p.exists():
                return p
        exact = root / f"{root.name}.{ext}"
        if exact.exists():
            return exact
        files = sorted(root.glob(f"*.{ext}"), key=lambda p: p.name.lower())
        return files[0] if files else None
    out["cmd"] = from_ref("cmd", "cmd")
    out["cns"] = from_ref("cns", "cns") or from_ref("st", "st")
    out["air"] = from_ref("anim", "air")
    out["sff"] = from_ref("sprite", "sff")
    out["snd"] = from_ref("sound", "snd")
    return out


def _all_code_files(root: Path) -> List[Path]:
    return [p for p in sorted(root.rglob("*"), key=lambda x: str(x).lower()) if p.is_file() and p.suffix.lower() in {".cmd", ".cns", ".st"}]


def _image_dimensions_from_payload(data: bytes, suffix: str) -> Optional[Tuple[int, int, Tuple[int, int, int, int] | None]]:
    try:
        from PIL import Image  # type: ignore
        from io import BytesIO
        im = Image.open(BytesIO(data))
        bbox = None
        if im.mode in {"RGBA", "LA"}:
            bbox = im.getbbox()
        else:
            # For PCX/opaque sprites, transparent index can vary, so keep full bounds.
            bbox = (0, 0, im.size[0], im.size[1])
        return im.size[0], im.size[1], bbox
    except Exception:
        return None


def _air_sprite_refs(air_path: Path) -> List[Tuple[int, int]]:
    refs: List[Tuple[int, int]] = []
    seen = set()
    if not air_path or not air_path.exists():
        return refs
    for action in parse_air(read_text_safely(air_path)):
        for frame in action.frames:
            key = (frame.group, frame.image)
            if frame.group < 0 or frame.image < 0 or key in seen:
                continue
            seen.add(key)
            refs.append(key)
    return refs


def factory_max_profile_report(root: Path) -> MaxResult:
    root = Path(root)
    result = MaxResult("Factory Max Profile Report")
    audit = scan_project(root)
    files = _discover_files(root)
    code_files = _all_code_files(root)
    actions = parse_air(read_text_safely(files["air"])) if files.get("air") and files["air"].exists() else []
    action_nums = {a.number for a in actions}
    missing_common = [f"{n} {COMMON_ANIMS[n]}" for n in COMMON_ANIMS if n not in action_nums]
    state_count = 0
    command_count = 0
    changestate_count = 0
    hitdef_count = 0
    target_states = set()
    defined_states = set()
    for p in code_files:
        scan = parse_code(read_text_safely(p))
        state_count += len(scan.states)
        command_count += len(scan.commands)
        for s in scan.states:
            defined_states.add(s.number)
        for c in scan.controllers:
            if c.stype == "changestate":
                changestate_count += 1
                val = c.values.get("value", "")
                if re.match(r"^-?\d+$", val):
                    target_states.add(int(val))
            if c.stype == "hitdef":
                hitdef_count += 1
    missing_targets = sorted(n for n in target_states if n not in defined_states and n not in {0, 20, 40, 50, 52})
    sff_variant = "none"
    sff_sprites = 0
    sff_extract = False
    if files.get("sff") and files["sff"].exists():
        try:
            sff = read_sff(files["sff"])
            sff_variant = sff.variant
            sff_sprites = len(sff.sprites)
            sff_extract = sff.is_supported_for_extraction
        except Exception as exc:
            result.warnings.append(f"SFF scan failed: {exc}")
    snd_sounds = 0
    if files.get("snd") and files["snd"].exists():
        try:
            snd_sounds = len(read_snd(files["snd"]).sounds)
        except Exception as exc:
            result.warnings.append(f"SND scan failed: {exc}")
    score = 100
    score -= min(32, len(audit.missing_required) * 8)
    score -= min(25, len(audit.missing_references) * 5)
    score -= min(22, len(missing_common))
    score -= min(22, len(missing_targets) * 2)
    if sff_sprites == 0:
        score -= 8
    if snd_sounds == 0:
        score -= 5
    score = max(0, score)
    lines = [
        f"# MugenForge Factory Max Report: {root.name}", "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}", "",
        f"Factory Max score: **{score}/100**", "",
        "## Core Files", "",
    ]
    for k in ["def", "cmd", "cns", "air", "sff", "snd"]:
        path = files.get(k)
        lines.append(f"- {k.upper()}: `{_rel(root, path) if path else 'missing'}`")
    lines += ["", "## Counts", "", f"- AIR actions: {len(actions)}", f"- Code files: {len(code_files)}", f"- Commands: {command_count}", f"- StateDefs: {state_count}", f"- ChangeStates: {changestate_count}", f"- HitDefs: {hitdef_count}", f"- SFF variant: {sff_variant}", f"- Parsed sprites: {sff_sprites}", f"- SFF extraction supported: {sff_extract}", f"- SND sounds: {snd_sounds}"]
    if audit.missing_required:
        lines += ["", "## Missing Required File Types", ""] + [f"- `{x}`" for x in audit.missing_required]
    if audit.missing_references:
        lines += ["", "## Missing DEF References", ""] + [f"- {x}" for x in audit.missing_references[:100]]
    if missing_common:
        lines += ["", "## Missing Common AIR Actions", ""] + [f"- {x}" for x in missing_common[:100]]
    if missing_targets:
        lines += ["", "## Missing State Targets", ""] + [f"- ChangeState target `{x}` has no local StateDef" for x in missing_targets[:100]]
    if audit.asset_issues:
        lines += ["", "## AIR/SFF Asset Issues", ""] + [f"- {x}" for x in audit.asset_issues[:100]]
    lines += ["", "## Better-than-FF Next Step", ""]
    if audit.missing_required or audit.missing_references:
        lines.append("Run **Factory Max One-Click Upgrade**. It repairs routing, installs no-code systems, generates missing placeholders, and writes docs.")
    elif missing_common:
        lines.append("Run **Auto CLSN / AIR Repair** or Factory+ missing actions, then rebuild placeholder SFF from AIR refs.")
    elif missing_targets:
        lines.append("Run **Write State Graph** and use Feature Bank presets to fill missing states.")
    else:
        lines.append("Structure is healthy. Replace placeholder art/audio, tune boxes, then package a release.")
    out = root / "MUGENFORGE_FACTORY_MAX_REPORT.md"
    _write(out, "\n".join(lines).strip() + "\n", result, root)
    result.notes.append(f"Score: {score}/100")
    result.notes.append("Report is written in plain English for non-coders.")
    return result


def write_codesense_bank(root: Path) -> MaxResult:
    root = Path(root)
    result = MaxResult("Factory Max CodeSense Bank")
    snippets = {
        "ChangeState safe return": {
            "purpose": "Return to idle when animation is over.",
            "block": "[State N, Return]\ntype = ChangeState\ntrigger1 = AnimTime = 0\nvalue = 0\nctrl = 1",
        },
        "HitDef starter": {
            "purpose": "Basic attack hit definition.",
            "block": "[State N, HitDef]\ntype = HitDef\ntrigger1 = AnimElem = 2\nattr = S, NA\ndamage = 35, 5\npausetime = 6, 8\nground.hittime = 12\nground.velocity = -3\nair.velocity = -2,-4",
        },
        "Projectile starter": {
            "purpose": "Simple projectile controller.",
            "block": "[State N, Projectile]\ntype = Projectile\ntrigger1 = AnimElem = 3\nprojanim = 1001\nprojhitanim = 1002\nprojremove = 1\nvelocity = 5,0\ndamage = 45,5",
        },
        "No-code variable timer": {
            "purpose": "Countdown variable used by installs, assists, cooldowns, and debug systems.",
            "block": "[State -2, Timer]\ntype = VarAdd\ntrigger1 = Var(10) > 0\nv = 10\nvalue = -1\nignorehitpause = 1",
        },
        "Training DisplayToClipboard": {
            "purpose": "Show useful test info while tuning.",
            "block": "[State -2, Debug]\ntype = DisplayToClipboard\ntrigger1 = 1\ntext = \"st=%d anim=%d elem=%d time=%d ctrl=%d pwr=%d\"\nparams = stateno, anim, animelemno(0), time, ctrl, power\nignorehitpause = 1",
        },
    }
    controllers = [
        "ChangeState", "HitDef", "Projectile", "Helper", "Explod", "PlaySnd", "VelSet", "VelAdd", "PosSet", "PosAdd", "VarSet", "VarAdd", "VarRandom", "PowerAdd", "LifeAdd", "PalFX", "AfterImage", "NotHitBy", "HitOverride", "ReversalDef", "AssertSpecial", "EnvShake", "ScreenBound", "TargetBind", "TargetState", "TargetLifeAdd", "SuperPause", "Pause", "DisplayToClipboard", "AppendToClipboard",
    ]
    triggers = [
        "Time", "AnimTime", "AnimElem", "AnimelemNo(0)", "Command", "Ctrl", "StateNo", "PrevStateNo", "MoveContact", "MoveHit", "MoveGuarded", "P2BodyDist X", "P2StateType", "P2MoveType", "Random", "AILevel", "Power", "Life", "RoundState", "NumHelper", "NumProj", "Var(n)", "FVar(n)",
    ]
    data = {
        "tool": "MugenForge Studio Factory Max",
        "version": FACTORY_MAX_VERSION,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "purpose": "Offline code-completion/snippet reference. Beginners choose presets; advanced users can copy snippets.",
        "controllers": controllers,
        "triggers": triggers,
        "snippets": snippets,
    }
    out_json = root / "MUGENFORGE_CODESENSE_BANK.json"
    out_md = root / "MUGENFORGE_CODESENSE_BANK.md"
    out_json.write_text(json.dumps(data, indent=2), encoding="utf-8")
    lines = ["# MugenForge CodeSense Bank", "", "Common controllers/triggers/snippets for safe M.U.G.E.N authoring.", "", "## Controllers", ""]
    lines += [f"- `{x}`" for x in controllers]
    lines += ["", "## Triggers", ""] + [f"- `{x}`" for x in triggers]
    lines += ["", "## Snippets", ""]
    for name, item in snippets.items():
        lines += [f"### {name}", "", item["purpose"], "", "```ini", item["block"], "```", ""]
    write_text_safely(out_md, "\n".join(lines).rstrip() + "\n")
    result.created_files += [_rel(root, out_json), _rel(root, out_md)]
    result.notes.append("This approximates an offline auto-completion/snippet database for creators who do not code.")
    return result


def write_state_graph(root: Path) -> MaxResult:
    root = Path(root)
    result = MaxResult("Factory Max State Graph")
    edges: List[Tuple[int, int, str]] = []
    states: Dict[int, Dict[str, str]] = {}
    commands: List[str] = []
    for p in _all_code_files(root):
        text = read_text_safely(p)
        scan = parse_code(text)
        commands += [c.name for c in scan.commands]
        current_state = None
        for state in scan.states:
            current_state = state.number
            states[state.number] = {"file": _rel(root, p), "anim": state.values.get("anim", "")}
            for ctrl in state.controllers:
                if ctrl.stype == "changestate":
                    val = ctrl.values.get("value", "")
                    if re.match(r"^-?\d+$", val):
                        label = ctrl.header
                        edges.append((state.number, int(val), label))
    # Also catch State -1 / -2 controllers parsed outside StateDefs poorly by parser.
    for p in _all_code_files(root):
        text = read_text_safely(p)
        sec = None
        for line in text.splitlines():
            m = re.match(r"\s*\[\s*Statedef\s+(-?\d+)\s*\]", line, re.I)
            if m:
                sec = int(m.group(1))
            vm = re.match(r"\s*value\s*=\s*(-?\d+)\b", line, re.I)
            if sec is not None and vm:
                edges.append((sec, int(vm.group(1)), "value"))
    out_dot = root / "MUGENFORGE_STATE_GRAPH.dot"
    out_md = root / "MUGENFORGE_STATE_GRAPH.md"
    dot = ["digraph MugenForgeStateGraph {", "  rankdir=LR;", "  node [shape=box];"]
    for s, meta in sorted(states.items()):
        label = f"{s}"
        if meta.get("anim"):
            label += f"\\nanim {meta['anim']}"
        dot.append(f"  s{s} [label=\"{label}\"];")
    for a, b, label in edges[:2000]:
        dot.append(f"  s{a} -> s{b} [label=\"{str(label)[:32].replace(chr(34), '')}\"];")
    dot.append("}")
    out_dot.write_text("\n".join(dot) + "\n", encoding="utf-8")
    lines = ["# MugenForge State Graph", "", f"States detected: {len(states)}", f"Edges detected: {len(edges)}", f"Commands detected: {len(set(commands))}", "", "## Edges", ""]
    for a, b, label in edges[:500]:
        lines.append(f"- `{a}` -> `{b}` ({label})")
    write_text_safely(out_md, "\n".join(lines).rstrip() + "\n")
    result.created_files += [_rel(root, out_dot), _rel(root, out_md)]
    result.notes.append("DOT graph can be opened by Graphviz or pasted into online DOT viewers.")
    return result


def write_organizer_manifest(root: Path) -> MaxResult:
    root = Path(root)
    result = MaxResult("Factory Max Organizer Manifest")
    rows = []
    for path in sorted(root.rglob("*"), key=lambda p: str(p).lower()):
        if path.is_dir():
            continue
        ext = path.suffix.lower()
        role = "other"
        if ext in {".def"}: role = "project routing"
        elif ext in {".air"}: role = "animations / CLSN"
        elif ext in {".cmd"}: role = "commands / inputs"
        elif ext in {".cns", ".st"}: role = "states / logic"
        elif ext == ".sff": role = "sprites"
        elif ext == ".snd": role = "sounds"
        elif ext == ".act": role = "palette"
        elif ext in IMAGE_SUFFIXES: role = "source image"
        elif ext in {".wav", ".ogg", ".mp3"}: role = "source audio"
        elif ext in {".md", ".txt", ".json", ".csv"}: role = "docs/data"
        rows.append([_rel(root, path), ext, role, path.stat().st_size, datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")])
    out_csv = root / "MUGENFORGE_ORGANIZER_MANIFEST.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["path", "extension", "role", "bytes", "modified"])
        w.writerows(rows)
    out_md = root / "MUGENFORGE_ORGANIZER_MANIFEST.md"
    counts: Dict[str, int] = {}
    for _, _, role, _, _ in rows:
        counts[role] = counts.get(role, 0) + 1
    lines = ["# MugenForge Organizer Manifest", "", "## File counts by role", ""]
    lines += [f"- {k}: {v}" for k, v in sorted(counts.items())]
    lines += ["", "## First 200 files", ""]
    lines += [f"- `{r[0]}` — {r[2]} — {int(r[3]):,} bytes" for r in rows[:200]]
    write_text_safely(out_md, "\n".join(lines).rstrip() + "\n")
    result.created_files += [_rel(root, out_csv), _rel(root, out_md)]
    return result


def suggest_clsn_from_sff(root: Path, padding: int = 2, save: bool = True) -> MaxResult:
    root = Path(root)
    result = MaxResult("Factory Max Auto CLSN From Sprites")
    files = _discover_files(root)
    air_path = files.get("air")
    sff_path = files.get("sff")
    if not air_path or not air_path.exists():
        result.warnings.append("No AIR file found.")
        return result
    if not sff_path or not sff_path.exists():
        result.warnings.append("No SFF file found.")
        return result
    try:
        sff = read_sff(sff_path)
        lookup = sprite_lookup(sff)
        data = sff_path.read_bytes()
    except Exception as exc:
        result.warnings.append(f"Could not inspect SFF: {exc}")
        return result
    size_cache: Dict[Tuple[int, int], Tuple[int, int, Tuple[int, int, int, int] | None, int, int]] = {}
    for key, spr in lookup.items():
        payload = data[spr.data_offset:spr.data_offset + spr.length]
        dims = _image_dimensions_from_payload(payload, spr.format_hint)
        if dims:
            size_cache[key] = (dims[0], dims[1], dims[2], spr.x, spr.y)
    old = read_text_safely(air_path)
    lines = old.splitlines()
    out: List[str] = []
    added = 0
    frame_re = re.compile(r"^\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)(.*)$")
    current_has_clsn = False
    for line in lines:
        if re.match(r"\s*Clsn[12]\s*:\s*\d+", line, re.I) or re.match(r"\s*Clsn[12]\s*\[", line, re.I):
            current_has_clsn = True
            out.append(line)
            continue
        m = frame_re.match(line)
        if m:
            g, i, fx, fy = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
            key = (g, i)
            if not current_has_clsn and key in size_cache:
                w, h, bbox, sx, sy = size_cache[key]
                if bbox:
                    bx1, by1, bx2, by2 = bbox
                else:
                    bx1, by1, bx2, by2 = (0, 0, w, h)
                x1 = bx1 - sx + fx + padding
                y1 = by1 - sy + fy + padding
                x2 = bx2 - sx + fx - padding
                y2 = by2 - sy + fy - padding
                # Body boxes should never be completely degenerate.
                if x2 <= x1: x2 = x1 + max(2, w - padding * 2)
                if y2 <= y1: y2 = y1 + max(2, h - padding * 2)
                out.append("Clsn2: 1 ; Factory Max auto-body box from sprite bounds")
                out.append(f"  Clsn2[0] = {x1},{y1},{x2},{y2}")
                added += 1
            out.append(line)
            current_has_clsn = False
            continue
        if re.match(r"\s*\[\s*Begin\s+Action", line, re.I):
            current_has_clsn = False
        out.append(line)
    if added and save:
        _backup(air_path)
        write_text_safely(air_path, "\n".join(out).rstrip() + "\n")
        result.changed_files.append(_rel(root, air_path))
    elif not added:
        result.skipped_files.append("No missing frame-level CLSN boxes were found, or SFF image dimensions could not be decoded.")
    result.notes.append(f"Auto body boxes added: {added}")
    result.notes.append("Generated boxes are a starting point. Use the visual CLSN editor to tune the fun/feel part.")
    return result


def retime_air(root: Path, tick_scale: float = 1.0, min_ticks: int = 1) -> MaxResult:
    root = Path(root)
    result = MaxResult("Factory Max AIR Retiming")
    files = _discover_files(root)
    air_path = files.get("air")
    if not air_path or not air_path.exists():
        result.warnings.append("No AIR file found.")
        return result
    scale = max(0.05, float(tick_scale))
    old = read_text_safely(air_path)
    frame_re = re.compile(r"^(\s*-?\d+\s*,\s*-?\d+\s*,\s*-?\d+\s*,\s*-?\d+\s*,\s*)(-?\d+)(.*)$")
    changed = 0
    def repl(m: re.Match[str]) -> str:
        nonlocal changed
        old_ticks = int(m.group(2))
        if old_ticks <= 0:
            return m.group(0)
        new_ticks = max(min_ticks, int(round(old_ticks * scale)))
        if new_ticks != old_ticks:
            changed += 1
        return f"{m.group(1)}{new_ticks}{m.group(3)}"
    new = "\n".join(frame_re.sub(repl, line) for line in old.splitlines()) + "\n"
    if changed:
        _backup(air_path)
        write_text_safely(air_path, new)
        result.changed_files.append(_rel(root, air_path))
    else:
        result.skipped_files.append("No frame ticks changed.")
    result.notes.append(f"Tick scale: {scale}")
    result.notes.append(f"Frame lines retimed: {changed}")
    return result


def renumber_air_actions(root: Path, offset: int = 10000) -> MaxResult:
    root = Path(root)
    result = MaxResult("Factory Max AIR Renumber Clone")
    files = _discover_files(root)
    air_path = files.get("air")
    if not air_path or not air_path.exists():
        result.warnings.append("No AIR file found.")
        return result
    old = read_text_safely(air_path)
    actions = parse_air(old)
    if not actions:
        result.warnings.append("AIR file has no actions to clone.")
        return result
    blocks: List[str] = ["", f"; Factory Max cloned action bank offset {offset}"]
    for action in actions:
        if action.number < 0:
            continue
        raw = "\n".join(action.raw_lines)
        cloned = re.sub(r"(\[\s*Begin\s+Action\s+)(-?\d+)(\s*\])", lambda m: f"{m.group(1)}{int(m.group(2))+offset}{m.group(3)}", raw, count=1, flags=re.I)
        # Also offset sprite group references only where group equals the old action number.
        cloned_lines = []
        frame_re = re.compile(r"^(\s*)(-?\d+)(\s*,\s*-?\d+\s*,.*)$")
        for line in cloned.splitlines():
            fm = frame_re.match(line)
            if fm and int(fm.group(2)) == action.number:
                cloned_lines.append(f"{fm.group(1)}{action.number + offset}{fm.group(3)}")
            else:
                cloned_lines.append(line)
        blocks.append("\n".join(cloned_lines))
    out_path = air_path.with_name(air_path.stem + f"_cloned_offset_{offset}.air")
    write_text_safely(out_path, old.rstrip() + "\n" + "\n\n".join(blocks).rstrip() + "\n")
    result.created_files.append(_rel(root, out_path))
    result.notes.append(f"Cloned {len(actions)} actions to new action numbers using offset {offset}.")
    return result


def create_storyboard_template(root: Path, name: str = "intro") -> MaxResult:
    root = Path(root)
    result = MaxResult("Factory Max Storyboard Template")
    safe = re.sub(r"[^A-Za-z0-9_\-]+", "_", name).strip("_") or "intro"
    folder = root / "storyboards"
    folder.mkdir(parents=True, exist_ok=True)
    def_path = folder / f"{safe}.def"
    text = f"""; MugenForge Factory Max storyboard starter
; Wire this in your character DEF [Arcade] as intro.storyboard or ending.storyboard.
[SceneDef]
spr = {safe}.sff
startscene = 0

[Scene 0]
fadein.time = 16
fadeout.time = 16
clearcolor = 0,0,0
layerall.pos = 0,0
layer0.anim = 0
end.time = 180

[Begin Action 0]
0,0, 0,0, 180
"""
    write_text_safely(def_path, text)
    result.created_files.append(_rel(root, def_path))
    result.notes.append("Creates the storyboard text scaffold. Add storyboard sprites/SFF later.")
    return result


def create_screenpack_template(root: Path) -> MaxResult:
    root = Path(root)
    result = MaxResult("Factory Max Screenpack Starter")
    folder = root / "screenpack_starter"
    folder.mkdir(exist_ok=True)
    system_def = folder / "system.def"
    fight_def = folder / "fight.def"
    select_def = folder / "select.def"
    write_text_safely(system_def, """; MugenForge screenpack starter
[Info]
name = MugenForge Starter Screenpack

[Files]
spr = system.sff
snd = system.snd
select = select.def
fight = fight.def

[Title Info]
menu.itemname.arcade = Arcade
menu.itemname.versus = VS Mode
menu.itemname.training = Training
""")
    write_text_safely(fight_def, """; MugenForge fight.def starter
[Files]
sff = fight.sff
snd = fight.snd

[Lifebar]
p1.pos = 40,20
p2.pos = 280,20
""")
    write_text_safely(select_def, """; MugenForge select.def starter
[Characters]
; Add characters like:
; chars/kfm/kfm.def

[ExtraStages]
""")
    result.created_files += [_rel(root, system_def), _rel(root, fight_def), _rel(root, select_def)]
    result.notes.append("Starter screenpack text only. Full motif editing still requires art/SFF/SND replacement.")
    return result


def create_sound_autobank(root: Path) -> MaxResult:
    root = Path(root)
    result = MaxResult("Factory Max Sound AutoBank")
    sounds_dir = root / "sounds"
    sounds_dir.mkdir(exist_ok=True)
    cues = [
        (0, 0, "system_ok"), (0, 1, "system_cancel"),
        (5, 0, "light_hit"), (5, 1, "medium_hit"), (5, 2, "heavy_hit"), (5, 3, "special_hit"), (5, 6, "super_hit"),
        (6, 0, "guard"), (7, 0, "jump"), (7, 1, "dash"), (7, 2, "land"),
        (10, 0, "voice_attack"), (10, 1, "voice_special"), (10, 2, "voice_super"), (10, 3, "voice_win"),
    ]
    cue_csv = sounds_dir / "mugenforge_sound_cues.csv"
    with cue_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["group", "index", "suggested_filename", "purpose"])
        for g, i, name in cues:
            w.writerow([g, i, f"{g}_{i}.wav", name])
    try:
        manifest = make_placeholder_sound_bank(sounds_dir)
        snd_path = root / f"{root.name}.snd"
        build_snd_from_manifest(manifest, snd_path)
        result.created_files += [_rel(root, cue_csv), _rel(root, manifest), _rel(root, snd_path)]
    except Exception as exc:
        result.created_files.append(_rel(root, cue_csv))
        result.warnings.append(f"Silent SND build failed: {exc}")
    result.notes.append("Replace silent WAVs with real sounds using the same filenames, then rebuild SND.")
    return result


def create_quick_test_suite(root: Path) -> MaxResult:
    root = Path(root)
    result = MaxResult("Factory Max Quick Test Suite")
    out = root / "MUGENFORGE_QUICK_TEST_SUITE.md"
    lines = [
        f"# Quick Test Suite: {root.name}", "",
        "Use this after every big edit.", "",
        "## Smoke test", "",
        "- Character loads without crashing.",
        "- Idle, walk, jump, crouch, guard, get-hit, fall, get-up all show sprites.",
        "- No red/blank sprite frames in common actions.",
        "- Sound effects play for light/medium/heavy/special/super placeholders.", "",
        "## Feel test", "",
        "- Every normal has startup, active, and recovery that feel intentional.",
        "- Every special has a reason to exist.",
        "- Every super spends meter or has a strong restriction.",
        "- CLSN2 body boxes are not too wide or too short.",
        "- CLSN1 attack boxes line up with the art, not the idea in your head.", "",
        "## Balance test", "",
        "- One safe poke, one anti-air, one punish, one movement option, one pressure option.",
        "- Zoners must have recovery. Rushdown must take risk. Grapplers must earn range.",
        "- Boss mode must still be readable, even if unfair by design.", "",
        "## Release test", "",
        "- Run Factory Max report.",
        "- Run State Graph.",
        "- Package release ZIP.",
    ]
    write_text_safely(out, "\n".join(lines).rstrip() + "\n")
    result.created_files.append(_rel(root, out))
    return result


def safe_import_from_project(root: Path, source: Path, mode: str = "copy") -> MaxResult:
    root = Path(root)
    source = Path(source)
    result = MaxResult("Factory Max Safe Project Import")
    if not source.exists() or not source.is_dir():
        result.warnings.append("Source project folder does not exist.")
        return result
    dest = root / "imports" / re.sub(r"[^A-Za-z0-9_\-]+", "_", source.name)
    dest.mkdir(parents=True, exist_ok=True)
    copied = []
    for p in sorted(source.rglob("*"), key=lambda x: str(x).lower()):
        if p.is_dir():
            continue
        rel = p.relative_to(source)
        if any(part.startswith(".") or part == "__pycache__" for part in rel.parts):
            continue
        if p.suffix.lower() in TEXT_SUFFIXES or p.suffix.lower() in IMAGE_SUFFIXES or p.suffix.lower() in {".sff", ".snd", ".act", ".wav", ".ogg"}:
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                target = target.with_name(target.stem + f"_import_{_now()}" + target.suffix)
            shutil.copy2(p, target)
            copied.append(_rel(root, target))
    manifest = dest / "MUGENFORGE_IMPORT_MANIFEST.json"
    manifest.write_text(json.dumps({
        "tool": "MugenForge Factory Max",
        "source": str(source),
        "destination": str(dest),
        "copied_files": copied,
        "note": "Safe import copies assets/code into an imports folder first. Merge manually or use Feature Bank to recreate behavior safely.",
    }, indent=2), encoding="utf-8")
    result.created_files += copied[:300]
    result.created_files.append(_rel(root, manifest))
    result.notes.append(f"Copied {len(copied)} files into imports/{dest.name}/ without overwriting the active character.")
    return result


def build_factory_max_release_zip(root: Path) -> MaxResult:
    root = Path(root)
    result = MaxResult("Factory Max Release ZIP")
    result.merge(factory_max_profile_report(root), "report")
    result.merge(write_organizer_manifest(root), "organizer")
    result.merge(write_state_graph(root), "state graph")
    result.merge(create_quick_test_suite(root), "test suite")
    exports = root / "exports"
    exports.mkdir(exist_ok=True)
    out = exports / f"{root.name}_factory_max_release_{_now()}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(root.rglob("*"), key=lambda p: str(p).lower()):
            if path.is_dir():
                continue
            rel = path.relative_to(root)
            rel_str = str(rel).replace("\\", "/")
            lower = rel_str.lower()
            if "__pycache__" in lower or ".git" in lower or ".bak_" in lower or lower.endswith((".pyc", ".tmp")):
                continue
            z.write(path, arcname=f"{root.name}/{rel_str}")
    result.created_files.append(_rel(root, out))
    result.notes.append("Release ZIP includes generated reports so testers know what changed and what is still placeholder.")
    return result


def one_click_factory_max_upgrade(root: Path) -> MaxResult:
    root = Path(root)
    result = MaxResult("Factory Max One-Click Better-than-FF Upgrade")
    # v2.4 Smart Complete first: file routing, placeholders, docs.
    result.merge(fp.smart_complete_project(root), "Factory+")
    for kit in [
        "FF+ Fighter Factory-Style Essentials",
        "FF+ Visual Polish Kit",
        "FF+ Combat Systems Kit",
        "FF+ Training and Debug Kit",
        "Max Visual Editor Parity Kit",
        "Max No-Code Combat Lab Kit",
        "Max Beginner Full Production Kit",
    ]:
        try:
            result.merge(apply_kit(root, kit), f"kit {kit}")
        except Exception as exc:
            result.warnings.append(f"Could not apply kit {kit}: {exc}")
    result.merge(write_codesense_bank(root), "codesense")
    result.merge(write_state_graph(root), "state graph")
    result.merge(write_organizer_manifest(root), "organizer")
    result.merge(create_sound_autobank(root), "sound bank")
    result.merge(create_quick_test_suite(root), "test suite")
    result.merge(factory_max_profile_report(root), "profile")
    result.notes.append("This pass intentionally favors no-code scaffolding and editable docs over risky binary mutation.")
    return result


def image_factory_process_folder(
    in_dir: Path,
    out_dir: Path,
    *,
    scale_percent: float = 100.0,
    trim: bool = True,
    mirror_x: bool = False,
    mirror_y: bool = False,
    canvas_w: int = 0,
    canvas_h: int = 0,
    center: bool = True,
    transparent_mode: str = "none",
    palette_colors: int = 0,
    outline: bool = False,
    shadow: bool = False,
) -> MaxResult:
    result = MaxResult("Factory Max Image Batch Processor")
    in_dir = Path(in_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageOps, ImageFilter  # type: ignore
    except Exception as exc:
        result.warnings.append(f"Pillow is required for image processing: {exc}")
        return result
    count = 0
    for src in sorted(in_dir.rglob("*"), key=lambda p: str(p).lower()):
        if src.is_dir() or src.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        try:
            im = Image.open(src).convert("RGBA")
            if transparent_mode == "top-left":
                key = im.getpixel((0, 0))
                pixels = im.load()
                for y in range(im.height):
                    for x in range(im.width):
                        if pixels[x, y][:3] == key[:3]:
                            pixels[x, y] = (pixels[x, y][0], pixels[x, y][1], pixels[x, y][2], 0)
            elif transparent_mode == "magenta":
                pixels = im.load()
                for y in range(im.height):
                    for x in range(im.width):
                        r, g, b, a = pixels[x, y]
                        if r > 230 and g < 40 and b > 230:
                            pixels[x, y] = (r, g, b, 0)
            if trim:
                bbox = im.getbbox()
                if bbox:
                    im = im.crop(bbox)
            if scale_percent and abs(scale_percent - 100.0) > 0.01:
                nw = max(1, int(round(im.width * scale_percent / 100.0)))
                nh = max(1, int(round(im.height * scale_percent / 100.0)))
                im = im.resize((nw, nh), Image.Resampling.NEAREST)
            if mirror_x:
                im = ImageOps.mirror(im)
            if mirror_y:
                im = ImageOps.flip(im)
            if outline:
                alpha = im.getchannel("A")
                grown = alpha.filter(ImageFilter.MaxFilter(3))
                outline_img = Image.new("RGBA", im.size, (0, 0, 0, 0))
                outline_img.putalpha(grown)
                outline_layer = Image.new("RGBA", im.size, (0, 0, 0, 255))
                outline_layer.putalpha(grown)
                final = Image.alpha_composite(outline_layer, im)
                im = final
            if shadow:
                shadow_alpha = im.getchannel("A").filter(ImageFilter.GaussianBlur(1.0))
                sh = Image.new("RGBA", (im.width + 4, im.height + 4), (0, 0, 0, 0))
                layer = Image.new("RGBA", im.size, (0, 0, 0, 110))
                layer.putalpha(shadow_alpha)
                sh.alpha_composite(layer, (4, 4))
                sh.alpha_composite(im, (0, 0))
                im = sh
            if canvas_w > 0 and canvas_h > 0:
                canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
                x = (canvas_w - im.width) // 2 if center else 0
                y = (canvas_h - im.height) // 2 if center else 0
                canvas.alpha_composite(im, (max(0, x), max(0, y)))
                im = canvas
            if palette_colors and 2 <= palette_colors <= 256:
                pal = im.convert("P", palette=Image.Palette.ADAPTIVE, colors=int(palette_colors))
                im = pal.convert("RGBA")
            rel = src.relative_to(in_dir)
            dst = out_dir / rel.with_suffix(".png")
            dst.parent.mkdir(parents=True, exist_ok=True)
            im.save(dst)
            result.created_files.append(str(dst))
            count += 1
        except Exception as exc:
            result.warnings.append(f"{src.name}: {exc}")
    result.notes.append(f"Processed images: {count}")
    return result


def make_palette_variants(folder: Path, out_dir: Path, variants: int = 6) -> MaxResult:
    result = MaxResult("Factory Max Palette Variant Maker")
    folder = Path(folder)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageEnhance  # type: ignore
    except Exception as exc:
        result.warnings.append(f"Pillow is required: {exc}")
        return result
    images = [p for p in sorted(folder.rglob("*"), key=lambda p: str(p).lower()) if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES]
    created = 0
    for src in images[:1000]:
        try:
            im = Image.open(src).convert("RGBA")
            for idx in range(max(1, variants)):
                sat = 0.75 + (idx * 0.16)
                con = 0.9 + (idx * 0.08)
                val = 0.85 + (idx * 0.05)
                mod = ImageEnhance.Color(im).enhance(sat)
                mod = ImageEnhance.Contrast(mod).enhance(con)
                mod = ImageEnhance.Brightness(mod).enhance(val)
                dst = out_dir / f"palette_{idx+1}" / src.relative_to(folder).with_suffix(".png")
                dst.parent.mkdir(parents=True, exist_ok=True)
                mod.save(dst)
                created += 1
        except Exception as exc:
            result.warnings.append(f"{src.name}: {exc}")
    result.notes.append(f"Palette variant images created: {created}")
    result.created_files.append(str(out_dir))
    return result
