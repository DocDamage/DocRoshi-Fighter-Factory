#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import compileall
import importlib
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print('MugenForge smoke root:', ROOT)
ok = compileall.compile_dir(str(ROOT / 'mugenforge'), quiet=1)
print('compileall:', 'PASS' if ok else 'FAIL')
if not ok:
    raise SystemExit(1)

import mugenforge
from mugenforge.app import APP_TITLE
print('version:', mugenforge.__version__)
print('title:', APP_TITLE)

for name in [
    'mugenforge.handoff_core', 'mugenforge.operator_console', 'mugenforge.evidence_core',
    'mugenforge.authority_core', 'mugenforge.runtime_lab', 'mugenforge.binary_maturity',
    'mugenforge.forge_timeline',
]:
    importlib.import_module(name)
    print('import:', name, 'PASS')

from mugenforge.parsers import make_new_character
from mugenforge.handoff_core import write_context_digest, write_package_inventory, write_regression_harness
from mugenforge.operator_console import write_operator_dashboard, write_next_chat_handoff, write_operator_roadmap
with tempfile.TemporaryDirectory(prefix='mf_v75_smoke_') as tmp:
    char = make_new_character(Path(tmp), 'SmokeHero')
    results = [
        write_context_digest(char),
        write_package_inventory(char),
        write_regression_harness(char),
        write_operator_dashboard(char),
        write_next_chat_handoff(char),
        write_operator_roadmap(char),
    ]
    print('backend warnings:', sum(len(r.warnings) for r in results))

print('SMOKE_TEST_PASS')
