"""Compatibility shim for older MugenForge modules.

v2.2+ moved the no-code workflow into no_code_director.py. Some optional
modules still import the old names, so this file routes those calls to the
newer implementations without exposing users to the refactor.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from .no_code_director import archetype_names, write_no_code_dashboard, no_code_director_summary, one_click_playable_skeleton
from .factory_plus import rebuild_placeholder_sff_from_air
from .snd_codec import make_placeholder_sound_bank, build_snd_from_manifest


def write_creator_profile(root: Path, archetype_name: str | None = None) -> Path:
    root = Path(root)
    write_no_code_dashboard(root, archetype_name)
    return root / "MUGENFORGE_CHARACTER_BLUEPRINT.json"


def build_placeholder_sff_from_air(root: Path) -> Path:
    root = Path(root)
    rebuild_placeholder_sff_from_air(root)
    return root / f"{root.name}.sff"


def build_placeholder_snd(root: Path) -> Path:
    root = Path(root)
    manifest = make_placeholder_sound_bank(root / "sounds")
    out = root / f"{root.name}.snd"
    build_snd_from_manifest(manifest, out)
    return out


def beginner_doctor_report(root: Path) -> str:
    return no_code_director_summary(Path(root), None)


def make_playable_prototype(root: Path, archetype_name: str | None = None):
    return one_click_playable_skeleton(Path(root), archetype_name)
