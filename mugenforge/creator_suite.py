from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import csv, json, re, zipfile
from typing import Dict, List, Optional, Sequence, Tuple

from .artifact_io import write_csv_artifact, write_text_artifact
from .parsers import parse_air, parse_code, parse_def, read_text_safely, scan_project, write_text_safely
from .sff_codec import read_sff, sprite_lookup
from .snd_codec import read_snd
from .automation_bank import auto_setup_project, apply_kit, kit_names, feature_bank_stats_text
from .factory_max import one_click_factory_max_upgrade, factory_max_profile_report, write_codesense_bank, write_state_graph

CREATOR_SUITE_VERSION = "3.2.0"
IMAGE_SUFFIXES = {".png", ".pcx", ".bmp", ".gif", ".jpg", ".jpeg", ".webp"}
SOUND_SUFFIXES = {".wav", ".ogg", ".mp3", ".flac", ".snd"}
PALETTE_SUFFIXES = {".act", ".pal"}
TEXT_SUFFIXES = {".def", ".air", ".cmd", ".cns", ".st", ".txt", ".md", ".json", ".ini", ".cfg"}

@dataclass
class SuiteResult:
    title: str = "Creator Suite Result"
    created_files: List[str] = field(default_factory=list)
    changed_files: List[str] = field(default_factory=list)
    skipped_files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    def merge(self, other: object, prefix: str = "") -> None:
        p = f"{prefix}: " if prefix else ""
        for attr in ("created_files", "changed_files", "skipped_files", "warnings", "notes"):
            for item in getattr(other, attr, []) or []:
                getattr(self, attr).append(p + str(item))
    def to_text(self) -> str:
        lines = [self.title, "=" * len(self.title), ""]
        for label, vals in [("Notes", self.notes), ("Created", self.created_files), ("Changed", self.changed_files), ("Skipped", self.skipped_files), ("Warnings", self.warnings)]:
            if vals:
                lines.append(label + ":")
                lines.extend(f"- {v}" for v in vals)
                lines.append("")
        if len(lines) <= 3:
            lines.append("No changes made.")
        return "\n".join(lines).rstrip() + "\n"

def _now() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def _rel(root: Path, path: Path | str) -> str:
    try: return str(Path(path).relative_to(root)).replace("\\", "/")
    except Exception: return str(path).replace("\\", "/")

def _backup(path: Path) -> None:
    if path.exists(): path.with_name(path.name + f".bak_{_now()}").write_bytes(path.read_bytes())

def _write(path: Path, text: str, result: Optional[SuiteResult] = None, root: Optional[Path] = None, changed: bool = False) -> Path:
    existed = path.exists()
    if existed and changed: _backup(path)
    return write_text_artifact(path, text, result, root, changed, track_existing=True, writer=write_text_safely)

def _append_once(path: Path, marker: str, block: str, result: SuiteResult, root: Path) -> None:
    existing = read_text_safely(path) if path.exists() else ""
    if marker in existing:
        result.skipped_files.append(f"{_rel(root, path)} already contains {marker}")
        return
    if path.exists(): _backup(path)
    write_text_safely(path, existing.rstrip() + "\n\n" + block.strip() + "\n")
    result.changed_files.append(_rel(root, path))

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
            files = parse_def(read_text_safely(out["def"])).get("files")
            if files: refs = {k.lower(): v.strip().strip('"') for k, v in files.values.items()}
        except Exception: refs = {}
    def f(key: str, ext: str) -> Optional[Path]:
        if key in refs:
            p = (root / refs[key]).resolve()
            if p.exists(): return p
        exact = root / f"{root.name}.{ext}"
        if exact.exists(): return exact
        matches = sorted(root.glob(f"*.{ext}"), key=lambda p: p.name.lower())
        return matches[0] if matches else None
    out["cmd"] = f("cmd", "cmd")
    out["cns"] = f("cns", "cns") or f("st", "st")
    out["air"] = f("anim", "air")
    out["sff"] = f("sprite", "sff")
    out["snd"] = f("sound", "snd")
    return out

def _code_files(root: Path) -> List[Path]:
    return [p for p in sorted(Path(root).rglob("*"), key=lambda x: str(x).lower()) if p.is_file() and p.suffix.lower() in {".cmd", ".cns", ".st"}]

def _img_size(path: Path) -> Tuple[str, str]:
    try:
        from PIL import Image  # type: ignore
        with Image.open(path) as im: return str(im.size[0]), str(im.size[1])
    except Exception: return "", ""

def _csv(path: Path, rows: Sequence[Dict[str, object]], fields: Sequence[str]) -> Path:
    return write_csv_artifact(path, rows, fields)

def _recipe(archetype: str, experience: str, button_layout: str, power_style: str) -> Dict[str, object]:
    kits = {
        "Balanced Starter": ["Starter Beginner Pack", "Six Button Normals", "Specials Toolkit", "Defense Toolkit", "Beginner Documentation Kit"],
        "Rushdown": ["Rushdown Archetype Kit", "Movement Toolkit", "Max Move Expansion Kit", "Max No-Code Combat Lab Kit"],
        "Zoner": ["Zoner Archetype Kit", "Specials Toolkit", "FF+ Combat Systems Kit", "Max AI and Training Kit"],
        "Grappler": ["Grappler Archetype Kit", "Grapple Toolkit", "Defense Toolkit", "Max No-Code Combat Lab Kit"],
        "Anime Movement": ["Anime Air-Movement Kit", "Movement Toolkit", "Max Move Expansion Kit", "FF+ Visual Polish Kit"],
        "Boss Prototype": ["Max AI and Training Kit", "FF+ AI and Boss Kit", "Supers and FX Toolkit"],
        "Full Creator": ["Full No-Code Creator Pack", "Max Beginner Full Production Kit", "Creator AutoPilot Full Kit"],
    }
    focus = {
        "Balanced Starter": ["clean basics", "safe six-button kit", "easy testing"],
        "Rushdown": ["dash pressure", "chain routes", "corner offense"],
        "Zoner": ["projectile lanes", "anti-air coverage", "screen control"],
        "Grappler": ["throws", "short-range reward", "readable risk"],
        "Anime Movement": ["air dashes", "double jumps", "fast fall"],
        "Boss Prototype": ["phase ideas", "strong supers", "AI routines"],
        "Full Creator": ["everything scaffolded", "docs-first production", "release dashboard"],
    }
    arch = archetype or "Balanced Starter"
    return {"version": CREATOR_SUITE_VERSION, "updated": datetime.now().isoformat(timespec="seconds"), "archetype": arch, "experience": experience or "Beginner", "button_layout": button_layout or "Six button", "power_style": power_style or "Standard meter", "recommended_kits": kits.get(arch, kits["Balanced Starter"]), "creative_focus": focus.get(arch, focus["Balanced Starter"]), "beginner_mode": True}

def write_character_dna_profile(root: Path, archetype: str = "Balanced Starter", experience: str = "Beginner", button_layout: str = "Six button", power_style: str = "Standard meter") -> SuiteResult:
    root = Path(root); root.mkdir(parents=True, exist_ok=True); r = SuiteResult("Character DNA Profile")
    data = _recipe(archetype, experience, button_layout, power_style)
    _write(root / "mugenforge_character_dna.json", json.dumps(data, indent=2), r, root, changed=(root / "mugenforge_character_dna.json").exists())
    lines = [f"# Character DNA: {root.name}", "", f"Generated: {data['updated']}", "", f"**Archetype:** {data['archetype']}", f"**Experience:** {data['experience']}", f"**Buttons:** {data['button_layout']}", f"**Power:** {data['power_style']}", "", "## Creative focus"]
    lines += [f"- {x}" for x in data["creative_focus"]]  # type: ignore[index]
    lines += ["", "## Recommended kits"] + [f"- {x}" for x in data["recommended_kits"]]  # type: ignore[index]
    lines += ["", "## Creator handles", "- Art", "- Sounds", "- Timing", "- Hitboxes", "- Personality", "- Play feel", "", "## MugenForge handles", "- Scaffolding", "- Reports", "- Backups", "- Placeholder assets", "- Release checklists"]
    _write(root / "docs" / "CHARACTER_DNA.md", "\n".join(lines) + "\n", r, root, changed=(root / "docs" / "CHARACTER_DNA.md").exists())
    r.notes.append("Character DNA is a no-code recipe for AutoPilot and kit selection.")
    return r

def write_asset_library(root: Path) -> SuiteResult:
    root = Path(root); r = SuiteResult("Creator Asset Library"); rows: List[Dict[str, object]] = []
    for p in sorted(root.rglob("*"), key=lambda x: str(x).lower()):
        if not p.is_file() or "__pycache__" in p.parts: continue
        suf = p.suffix.lower(); cat = "other"
        if suf in IMAGE_SUFFIXES: cat = "image"
        elif suf in SOUND_SUFFIXES: cat = "sound"
        elif suf in PALETTE_SUFFIXES: cat = "palette"
        elif suf in TEXT_SUFFIXES: cat = "text"
        w, h = _img_size(p) if cat == "image" else ("", "")
        rows.append({"path": _rel(root, p), "category": cat, "suffix": suf, "bytes": p.stat().st_size, "width": w, "height": h, "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")})
    out = root / "reports"; fields = ["path", "category", "suffix", "bytes", "width", "height", "modified"]
    _csv(out / "asset_library.csv", rows, fields); r.created_files.append("reports/asset_library.csv")
    files = _discover_files(root); notes: List[str] = []
    if files.get("sff"):
        try: notes.append(f"SFF sprites: {len(read_sff(files['sff']).sprites)}")
        except Exception as e: notes.append(f"SFF scan failed: {e}")
    if files.get("snd"):
        try: notes.append(f"SND sounds: {len(read_snd(files['snd']).sounds)}")
        except Exception as e: notes.append(f"SND scan failed: {e}")
    _write(out / "asset_library.json", json.dumps({"version": CREATOR_SUITE_VERSION, "assets": rows, "notes": notes}, indent=2), r, root, changed=(out / "asset_library.json").exists())
    counts: Dict[str, int] = {}
    for row in rows: counts[str(row["category"])] = counts.get(str(row["category"]), 0) + 1
    md = [f"# Asset Library: {root.name}", "", "## Counts"] + [f"- {k}: {v}" for k, v in sorted(counts.items())] + ["", "## Binary notes"] + [f"- {n}" for n in notes]
    md += ["", "## Assets"] + [f"- `{row['path']}` — {row['category']} {row['bytes']} bytes" for row in rows[:250]]
    _write(out / "ASSET_LIBRARY.md", "\n".join(md) + "\n", r, root, changed=(out / "ASSET_LIBRARY.md").exists())
    r.notes.append(f"Indexed {len(rows)} files.")
    return r

def _commands(cmd: Optional[Path]) -> Dict[str, str]:
    if not cmd or not cmd.exists(): return {}
    out: Dict[str, str] = {}; name = None; val = None
    for line in read_text_safely(cmd).splitlines():
        m = re.match(r'\s*name\s*=\s*"?([^";]+)"?', line, re.I)
        if m: name = m.group(1).strip()
        m = re.match(r'\s*command\s*=\s*(.+)', line, re.I)
        if m: val = m.group(1).split(';', 1)[0].strip()
        if name and val: out[name] = val; name = val = None
    return out

def write_move_lab(root: Path) -> SuiteResult:
    root = Path(root); r = SuiteResult("Move Lab / Frame Sheet"); files = _discover_files(root); air_map = {}
    if files.get("air") and files["air"].exists(): air_map = {a.number: a for a in parse_air(read_text_safely(files["air"]))}
    rows: List[Dict[str, object]] = []
    for p in _code_files(root):
        scan = parse_code(read_text_safely(p))
        for s in scan.states:
            anim = s.values.get("anim", "")
            try: a = air_map.get(int(str(anim).strip()))
            except Exception: a = None
            controllers = [c.stype for c in s.controllers]
            rows.append({"state": s.number, "file": _rel(root, p), "line": s.line, "anim": anim, "air_frames": len(a.frames) if a else "", "air_ticks": sum(max(0, f.ticks) for f in a.frames) if a else "", "has_hitdef": "yes" if "hitdef" in controllers else "", "controllers": len(controllers), "type": s.values.get("type", ""), "movetype": s.values.get("movetype", ""), "physics": s.values.get("physics", "")})
    out = root / "reports"; fields = ["state", "file", "line", "anim", "air_frames", "air_ticks", "has_hitdef", "controllers", "type", "movetype", "physics"]
    _csv(out / "move_lab.csv", rows, fields); r.created_files.append("reports/move_lab.csv")
    cmd = _commands(files.get("cmd"))
    md = [f"# Move Lab: {root.name}", "", "## Commands"] + ([f"- `{k}` → `{v}`" for k, v in sorted(cmd.items())] or ["- No commands found yet."]) + ["", "## States"]
    md += [f"- State `{x['state']}` anim `{x['anim']}` frames `{x['air_frames']}` ticks `{x['air_ticks']}` hitdef `{x['has_hitdef'] or 'no'}`" for x in rows[:300]] or ["- No states found yet."]
    md += ["", "## Beginner interpretation", "- Lower total ticks usually means faster animation.", "- HitDef states are attack-like states.", "- Empty AIR frames means the state points to an animation that may not exist."]
    _write(out / "MOVE_LAB.md", "\n".join(md) + "\n", r, root, changed=(out / "MOVE_LAB.md").exists())
    r.notes.append(f"Mapped {len(rows)} states/moves.")
    return r

def write_combo_tree(root: Path) -> SuiteResult:
    root = Path(root); r = SuiteResult("Combo Tree"); states: Dict[int, str] = {}; edges: List[Tuple[int, int, str]] = []
    for p in _code_files(root):
        scan = parse_code(read_text_safely(p))
        for s in scan.states:
            states[s.number] = _rel(root, p)
            for c in s.controllers:
                if c.stype == "changestate":
                    val = c.values.get("value", "")
                    if re.match(r"^-?\d+$", str(val).strip()): edges.append((s.number, int(str(val).strip()), c.header))
    out = root / "reports"; dot = ["digraph MugenForgeComboTree {", "rankdir=LR;", "node [shape=box];"]
    for n, f in sorted(states.items()): dot.append(f's{n} [label="{n}\\n{f}"];')
    for a, b, label in edges[:1000]: dot.append(f's{a} -> s{b} [label="{label.replace(chr(34), chr(39))[:40]}"];')
    dot.append("}"); _write(out / "combo_tree.dot", "\n".join(dot) + "\n", r, root, changed=(out / "combo_tree.dot").exists())
    md = [f"# Combo / State Flow Tree: {root.name}", "", "## Edges"] + ([f"- `{a}` → `{b}` via `{label}`" for a, b, label in edges[:300]] or ["- No ChangeState edges found."])
    _write(out / "COMBO_TREE.md", "\n".join(md) + "\n", r, root, changed=(out / "COMBO_TREE.md").exists())
    r.notes.append(f"Found {len(edges)} ChangeState links.")
    return r

def write_art_task_board(root: Path) -> SuiteResult:
    root = Path(root); r = SuiteResult("Art Task Board"); files = _discover_files(root); actions = []
    if files.get("air") and files["air"].exists(): actions = parse_air(read_text_safely(files["air"]))
    keys = set()
    if files.get("sff") and files["sff"].exists():
        try: keys = set(sprite_lookup(read_sff(files["sff"])).keys())
        except Exception as e: r.warnings.append(f"SFF lookup failed: {e}")
    rows: List[Dict[str, object]] = []
    for a in actions:
        for i, fr in enumerate(a.frames):
            if fr.group < 0 or fr.image < 0: continue
            ok = (fr.group, fr.image) in keys
            rows.append({"action": a.number, "frame": i, "group": fr.group, "image": fr.image, "ticks": fr.ticks, "status": "exists" if ok else "missing/placeholder needed", "artist_note": "review polish" if ok else "replace placeholder art"})
    out = root / "reports"; fields = ["action", "frame", "group", "image", "ticks", "status", "artist_note"]
    _csv(out / "art_task_board.csv", rows, fields); r.created_files.append("reports/art_task_board.csv")
    missing = [x for x in rows if str(x["status"]).startswith("missing")]
    md = [f"# Art Task Board: {root.name}", "", f"AIR sprite references: {len(rows)}", f"Missing/placeholder-needed frames: {len(missing)}", "", "## Priority frames"]
    md += [f"- Action `{x['action']}` frame `{x['frame']}` needs sprite `{x['group']},{x['image']}`" for x in missing[:200]] or ["- No missing refs detected against supported SFF scan."]
    _write(out / "ART_TASK_BOARD.md", "\n".join(md) + "\n", r, root, changed=(out / "ART_TASK_BOARD.md").exists())
    r.notes.append(f"Wrote {len(rows)} AIR frame tasks.")
    return r

def install_beginner_tuning_panel(root: Path) -> SuiteResult:
    root = Path(root); r = SuiteResult("Beginner Tuning Panel"); files = _discover_files(root); cns = files.get("cns") or (root / f"{root.name}.cns")
    knobs = {"version": CREATOR_SUITE_VERSION, "damage_scale_percent": 100, "hit_pause_ticks": 8, "guard_pause_ticks": 6, "pushback_x": -4, "beginner_note": "Generated moves can read these values in future no-code systems; hand-authored HitDefs may need manual tuning."}
    _write(root / "data" / "mugenforge_tuning_knobs.json", json.dumps(knobs, indent=2), r, root, changed=(root / "data" / "mugenforge_tuning_knobs.json").exists())
    marker = "; MUGENFORGE_TUNING_PANEL_V26"
    block = f"""{marker}
; Beginner-readable central tuning flags.
[State -2, MugenForge tuning damage scale note]
type = VarSet
trigger1 = RoundState >= 0
v = 59
value = 100
ignorehitpause = 1

[State -2, MugenForge tuning debug]
type = AppendToClipboard
trigger1 = 0 ; set to 1 while testing tuning vars
text = "\\nMugenForge tuning damage scale=%d"
params = Var(59)
ignorehitpause = 1
; END MUGENFORGE_TUNING_PANEL_V26
"""
    _append_once(cns, marker, block, r, root)
    return r

def make_project_time_machine_snapshot(root: Path) -> SuiteResult:
    root = Path(root); r = SuiteResult("Project Time Machine Snapshot"); snap = root / "snapshots"; snap.mkdir(parents=True, exist_ok=True); out = snap / f"{root.name}_snapshot_{_now()}.zip"; manifest = []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(root.rglob("*"), key=lambda x: str(x).lower()):
            if not p.is_file(): continue
            rel = _rel(root, p)
            if rel.startswith("snapshots/") or "__pycache__" in rel or rel.endswith(".pyc"): continue
            zf.write(p, arcname=rel); manifest.append({"path": rel, "bytes": p.stat().st_size})
    man = out.with_suffix(".manifest.json"); man.write_text(json.dumps({"version": CREATOR_SUITE_VERSION, "snapshot": out.name, "files": manifest}, indent=2), encoding="utf-8")
    r.created_files += [_rel(root, out), _rel(root, man)]; r.notes.append(f"Snapshot captured {len(manifest)} files.")
    return r

def write_creator_dashboard(root: Path) -> SuiteResult:
    root = Path(root); r = SuiteResult("Creator Dashboard"); audit = scan_project(root); reports = sorted((root / "reports").glob("*")) if (root / "reports").exists() else []; docs = sorted((root / "docs").glob("*")) if (root / "docs").exists() else []
    status = "Needs setup" if audit.missing_required else "Playable structure present"
    html = ["<!doctype html><html><head><meta charset='utf-8'><title>MugenForge Dashboard</title><style>body{font-family:Arial;margin:32px;line-height:1.45}code{background:#eee;padding:2px 4px}.bad{color:#a00}.ok{color:#070}</style></head><body>", f"<h1>MugenForge Creator Dashboard: {root.name}</h1>", f"<p><b>Status:</b> <span class='{ 'bad' if audit.missing_required else 'ok' }'>{status}</span></p>", "<h2>Next best actions</h2><ol>"]
    if audit.missing_required: html.append("<li>Run Creator AutoPilot or Factory Max Upgrade to repair required files.</li>")
    if audit.asset_issues: html.append("<li>Open Art Task Board and replace/build missing sprites.</li>")
    if audit.code_issues: html.append("<li>Open CodeSense/Move Lab and fix missing commands/states.</li>")
    html += ["<li>Use Animation Player and CLSN Editor to tune feel.</li><li>Run final QA before release.</li></ol><h2>Reports</h2><ul>"]
    html += [f"<li><code>{_rel(root,p)}</code></li>" for p in reports] + ["</ul><h2>Docs</h2><ul>"] + [f"<li><code>{_rel(root,p)}</code></li>" for p in docs] + ["</ul></body></html>"]
    _write(root / "MUGENFORGE_DASHBOARD.html", "\n".join(html) + "\n", r, root, changed=(root / "MUGENFORGE_DASHBOARD.html").exists())
    md = [f"# Creator Dashboard: {root.name}", "", f"Status: **{status}**", "", "## Health", f"- Missing required: {', '.join(audit.missing_required) or 'none'}", f"- Missing DEF refs: {len(audit.missing_references)}", f"- AIR/SFF asset issues: {len(audit.asset_issues)}", f"- Code issues: {len(audit.code_issues)}"]
    _write(root / "MUGENFORGE_DASHBOARD.md", "\n".join(md) + "\n", r, root, changed=(root / "MUGENFORGE_DASHBOARD.md").exists())
    return r

def write_final_qa_release_plan(root: Path) -> SuiteResult:
    root = Path(root); r = SuiteResult("Final QA / Release Plan"); audit = scan_project(root); issues = [f"Missing {x}" for x in audit.missing_required] + audit.missing_references + audit.asset_issues[:100] + audit.code_issues[:100]
    checks = ["Open every main action in Animation Player.", "Drag hitboxes until they match sprites.", "Test idle, walk, jump, guard, get-hit, attacks, specials, supers, intro, win, lose.", "Check sound volume consistency.", "Credit all sources.", "Build a clean release ZIP."]
    md = [f"# Final QA / Release Plan: {root.name}", "", "## Blockers"] + ([f"- {x}" for x in issues] or ["- No obvious automated blockers."]) + ["", "## Manual test checklist"] + [f"- [ ] {x}" for x in checks]
    _write(root / "MUGENFORGE_FINAL_QA.md", "\n".join(md) + "\n", r, root, changed=(root / "MUGENFORGE_FINAL_QA.md").exists())
    r.notes.append(f"QA plan includes {len(issues)} automated blocker lines.")
    return r

def write_training_pack(root: Path) -> SuiteResult:
    root = Path(root); r = SuiteResult("Training / Tutorial Pack"); out = root / "docs" / "training"
    files = {
        "BUTTON_GUIDE.md": "# Button Guide\n\n- x: light punch\n- y: medium punch\n- z: heavy punch\n- a: light kick\n- b: medium kick\n- c: heavy kick\n- s: taunt/start\n",
        "COMBO_TRIALS.md": "# Combo Trials\n\n- Trial 1: light normal → medium normal\n- Trial 2: jump-in → normal → special\n- Trial 3: punish starter → super\n",
        "TESTING_SCRIPT.md": "# Live Testing Script\n\n- Does the command work?\n- Does the sprite appear?\n- Does the hitbox match?\n- Is it fair on block/whiff?\n- Does it return to idle?\n",
    }
    for name, text in files.items(): _write(out / name, text, r, root, changed=(out / name).exists())
    return r

def write_creator_indexes(root: Path) -> SuiteResult:
    r = SuiteResult("Creator Indexes")
    for fn, label in [(write_asset_library, "assets"), (write_move_lab, "moves"), (write_combo_tree, "combos"), (write_art_task_board, "art"), (write_creator_dashboard, "dashboard")]:
        try: r.merge(fn(root), label)
        except Exception as e: r.warnings.append(f"{label} failed: {e}")
    return r

def one_click_creator_autopilot(root: Path, archetype: str = "Balanced Starter", experience: str = "Beginner", button_layout: str = "Six button", power_style: str = "Standard meter") -> SuiteResult:
    root = Path(root); root.mkdir(parents=True, exist_ok=True); r = SuiteResult("One-Click Creator AutoPilot")
    for fn, label in [(make_project_time_machine_snapshot, "snapshot-before"), (auto_setup_project, "setup")]:
        try: r.merge(fn(root), label)
        except Exception as e: r.warnings.append(f"{label} failed: {e}")
    r.merge(write_character_dna_profile(root, archetype, experience, button_layout, power_style), "dna")
    available = set(kit_names()); recipe = _recipe(archetype, experience, button_layout, power_style)
    for kit in recipe.get("recommended_kits", []):
        if kit in available:
            try: r.merge(apply_kit(root, str(kit)), f"kit {kit}")
            except Exception as e: r.warnings.append(f"Kit failed ({kit}): {e}")
        else: r.skipped_files.append(f"Kit unavailable: {kit}")
    for fn, label in [(one_click_factory_max_upgrade, "factory-max"), (write_codesense_bank, "codesense"), (write_state_graph, "state-graph"), (write_creator_indexes, "indexes"), (install_beginner_tuning_panel, "tuning"), (write_training_pack, "training"), (write_final_qa_release_plan, "qa")]:
        try: r.merge(fn(root), label)
        except Exception as e: r.warnings.append(f"{label} failed: {e}")
    r.notes.append("AutoPilot finished. Open MUGENFORGE_DASHBOARD.html or reports/MOVE_LAB.md for next creative steps.")
    return r

def creator_suite_profile_report(root: Path) -> SuiteResult:
    r = SuiteResult("Creator Suite Profile Report")
    for fn, label in [(factory_max_profile_report, "factory-max"), (write_creator_indexes, "indexes")]:
        try: r.merge(fn(root), label)
        except Exception as e: r.warnings.append(f"{label} failed: {e}")
    try: _write(Path(root) / "reports" / "FEATURE_BANK_STATS.txt", feature_bank_stats_text(), r, Path(root), changed=(Path(root) / "reports" / "FEATURE_BANK_STATS.txt").exists())
    except Exception as e: r.warnings.append(f"Feature bank stats failed: {e}")
    return r

# ---------------------------------------------------------------------------
# v3.2 no-code tuning and handoff extensions
# ---------------------------------------------------------------------------

HITDEF_TUNING_FIELDS = [
    "damage", "pausetime", "guard.pausetime", "sparkno", "guard.sparkno",
    "ground.velocity", "air.velocity", "guard.velocity", "hitflag", "guardflag",
    "priority", "fall", "animtype", "air.animtype", "ground.type",
]


def _hitdef_blocks_for_sheet(path: Path) -> List[Dict[str, object]]:
    text = read_text_safely(path)
    lines = text.splitlines()
    sections: List[Tuple[int, str]] = []
    sec_re = re.compile(r"^\s*\[\s*([^\]]+)\s*\]")
    for i, line in enumerate(lines):
        m = sec_re.match(line)
        if m:
            sections.append((i, m.group(1).strip()))
    blocks: List[Dict[str, object]] = []
    current_state = ""
    for idx, (start, header) in enumerate(sections):
        low = header.lower()
        m_state = re.match(r"statedef\s+(-?\d+)", low, re.I)
        if m_state:
            current_state = m_state.group(1)
            continue
        if not low.startswith("state"):
            continue
        end = sections[idx + 1][0] if idx + 1 < len(sections) else len(lines)
        block_lines = lines[start:end]
        values: Dict[str, str] = {}
        for line in block_lines[1:]:
            kv = re.match(r"^\s*([^;=]+?)\s*=\s*(.*?)\s*(?:;.*)?$", line)
            if kv:
                values[kv.group(1).strip().lower()] = kv.group(2).strip()
        if values.get("type", "").lower() == "hitdef":
            blocks.append({"path": path, "start": start, "end": end, "line": start + 1, "state": current_state, "header": header, "values": values})
    return blocks


def export_hitdef_tuning_sheet(root: Path) -> SuiteResult:
    root = Path(root)
    r = SuiteResult("HitDef Tuning Sheet Export")
    rows: List[Dict[str, object]] = []
    for path in _code_files(root):
        for block in _hitdef_blocks_for_sheet(path):
            vals: Dict[str, str] = block.get("values", {})  # type: ignore[assignment]
            row: Dict[str, object] = {"apply": "yes", "file": _rel(root, path), "state": block.get("state", ""), "controller_line": block.get("line", ""), "controller_header": block.get("header", ""), "designer_note": "edit values, then use Apply HitDef Tuning Sheet"}
            for key in HITDEF_TUNING_FIELDS:
                row[key] = vals.get(key, "")
            rows.append(row)
    out_dir = root / "reports"
    fields = ["apply", "file", "state", "controller_line", "controller_header"] + HITDEF_TUNING_FIELDS + ["designer_note"]
    _csv(out_dir / "hitdef_tuning_sheet.csv", rows, fields)
    r.created_files.append("reports/hitdef_tuning_sheet.csv")
    md = [f"# HitDef Tuning Sheet: {root.name}", "", "Open `reports/hitdef_tuning_sheet.csv`, edit beginner-readable HitDef values, then press **Apply HitDef Tuning Sheet**. Backups are written before changes.", "", f"Detected HitDefs: **{len(rows)}**", "", "## Editable fields"] + [f"- `{k}`" for k in HITDEF_TUNING_FIELDS]
    _write(out_dir / "HITDEF_TUNING_SHEET.md", "\n".join(md) + "\n", r, root, changed=(out_dir / "HITDEF_TUNING_SHEET.md").exists())
    r.notes.append(f"Exported {len(rows)} HitDef rows.")
    return r


def _truthy_apply(value: object) -> bool:
    return str(value).strip().lower() not in {"", "0", "no", "false", "skip", "off"}


def _update_key_in_block(lines: List[str], start: int, end: int, key: str, value: str) -> Tuple[int, int]:
    value = str(value or "").strip()
    if value == "":
        return end, 0
    key_re = re.compile(rf"^(\s*){re.escape(key)}(\s*=).*$", re.I)
    for i in range(start + 1, end):
        if key_re.match(lines[i]):
            new_line = f"{key} = {value}"
            if lines[i] != new_line:
                lines[i] = new_line
                return end, 1
            return end, 0
    lines.insert(end, f"{key} = {value}")
    return end + 1, 1


def apply_hitdef_tuning_sheet(root: Path, sheet_path: Optional[Path] = None) -> SuiteResult:
    root = Path(root)
    r = SuiteResult("Apply HitDef Tuning Sheet")
    sheet = Path(sheet_path) if sheet_path else root / "reports" / "hitdef_tuning_sheet.csv"
    if not sheet.exists():
        r.warnings.append(f"Missing tuning sheet: {_rel(root, sheet)}. Run Export HitDef Tuning Sheet first.")
        return r
    with sheet.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    by_file: Dict[str, List[Dict[str, str]]] = {}
    for row in rows:
        if not _truthy_apply(row.get("apply", "yes")):
            r.skipped_files.append(f"Skipped row for {row.get('file')} line {row.get('controller_line')}")
            continue
        rel = (row.get("file") or "").strip()
        if rel:
            by_file.setdefault(rel, []).append(row)
    changed_count = 0
    for rel, file_rows in by_file.items():
        path = root / rel
        if not path.exists():
            r.warnings.append(f"Cannot apply tuning; file missing: {rel}")
            continue
        lines = read_text_safely(path).splitlines()
        file_changed = 0
        def rowline(row: Dict[str, str]) -> int:
            m = re.search(r"\d+", row.get("controller_line", "0") or "0")
            return int(m.group(0)) if m else 0
        for row in sorted(file_rows, key=rowline, reverse=True):
            start = rowline(row) - 1
            if start < 0 or start >= len(lines) or not re.match(r"^\s*\[", lines[start]):
                header = str(row.get("controller_header", "")).strip().lower()
                start = next((i for i, ln in enumerate(lines) if header and ln.strip().lower().strip("[]") == header), -1)
            if start < 0:
                r.warnings.append(f"Could not locate HitDef block in {rel} for row line {row.get('controller_line')}")
                continue
            end = start + 1
            while end < len(lines) and not re.match(r"^\s*\[", lines[end]):
                end += 1
            block_text = "\n".join(lines[start:end]).lower()
            if "type" not in block_text or "hitdef" not in block_text:
                r.warnings.append(f"Located block is not a HitDef in {rel} line {start + 1}")
                continue
            for key in HITDEF_TUNING_FIELDS:
                end, n = _update_key_in_block(lines, start, end, key, str(row.get(key, "")).strip())
                file_changed += n
        if file_changed:
            _backup(path)
            write_text_safely(path, "\n".join(lines).rstrip() + "\n")
            r.changed_files.append(rel)
            changed_count += file_changed
    report = [f"# Applied HitDef Tuning: {root.name}", "", f"Applied: {datetime.now().isoformat(timespec='seconds')}", f"Field changes/additions: {changed_count}", "", f"Source sheet: `{_rel(root, sheet)}`"]
    _write(root / "reports" / "APPLIED_HITDEF_TUNING.md", "\n".join(report) + "\n", r, root, changed=(root / "reports" / "APPLIED_HITDEF_TUNING.md").exists())
    r.notes.append(f"Applied {changed_count} HitDef field changes/additions.")
    return r


def write_artist_handoff_pack(root: Path) -> SuiteResult:
    root = Path(root)
    r = SuiteResult("Artist / Sound Handoff Pack")
    files = _discover_files(root)
    out = root / "handoff" / "artist_sound_pack"
    out.mkdir(parents=True, exist_ok=True)
    sprite_keys = set()
    if files.get("sff") and files["sff"].exists():
        try:
            sprite_keys = set(sprite_lookup(read_sff(files["sff"])) .keys())
        except Exception as e:
            r.warnings.append(f"SFF scan failed: {e}")
    sprite_rows: List[Dict[str, object]] = []
    if files.get("air") and files["air"].exists():
        for a in parse_air(read_text_safely(files["air"])):
            for idx, fr in enumerate(a.frames):
                if fr.group < 0 or fr.image < 0:
                    continue
                exists = (fr.group, fr.image) in sprite_keys
                sprite_rows.append({"action": a.number, "frame": idx, "group": fr.group, "image": fr.image, "ticks": fr.ticks, "status": "exists" if exists else "missing_or_placeholder", "suggested_filename": f"g{fr.group}_i{fr.image}.png", "artist_note": "replace/polish" if exists else "draw/import needed"})
    _csv(out / "sprite_replacement_queue.csv", sprite_rows, ["action", "frame", "group", "image", "ticks", "status", "suggested_filename", "artist_note"])
    r.created_files.append(_rel(root, out / "sprite_replacement_queue.csv"))
    sound_keys = set()
    if files.get("snd") and files["snd"].exists():
        try:
            sound_keys = {(s.group, s.sound) for s in read_snd(files["snd"]).sounds if s.group is not None and s.sound is not None}
        except Exception as e:
            r.warnings.append(f"SND scan failed: {e}")
    sound_rows: List[Dict[str, object]] = []
    for path in _code_files(root):
        scan = parse_code(read_text_safely(path))
        for state in scan.states:
            for ctrl in state.controllers:
                if (ctrl.stype or ctrl.values.get("type", "")).lower() != "playsnd":
                    continue
                nums = re.findall(r"-?\d+", ctrl.values.get("value", ""))
                if len(nums) >= 2:
                    g, s = int(nums[0]), int(nums[1])
                    sound_rows.append({"file": _rel(root, path), "state": state.number, "line": ctrl.line, "group": g, "sound": s, "status": "exists" if (g, s) in sound_keys else "missing_or_placeholder", "suggested_filename": f"sound_{g}_{s}.wav", "sound_note": "replace/polish" if (g, s) in sound_keys else "record/import needed"})
    _csv(out / "sound_replacement_queue.csv", sound_rows, ["file", "state", "line", "group", "sound", "status", "suggested_filename", "sound_note"])
    r.created_files.append(_rel(root, out / "sound_replacement_queue.csv"))
    readme = [f"# Artist / Sound Handoff Pack: {root.name}", "", "Use this folder when the creator wants to focus on the fun parts instead of code.", "", "## Sprite workflow", "1. Open `sprite_replacement_queue.csv`.", "2. Create/replace files using suggested names like `g200_i0.png`.", "3. Use Sprite Lab or Sheet Import to build the SFF/AIR.", "", "## Sound workflow", "1. Open `sound_replacement_queue.csv`.", "2. Record/export WAVs using names like `sound_5_0.wav`.", "3. Use the Sounds tab to build the SND.", "", f"Sprite tasks: {len(sprite_rows)}", f"Sound tasks: {len(sound_rows)}"]
    _write(out / "README_ARTIST_SOUND_HANDOFF.md", "\n".join(readme) + "\n", r, root, changed=(out / "README_ARTIST_SOUND_HANDOFF.md").exists())
    r.notes.append("Handoff pack created for art/sound replacement without code editing.")
    return r
