from __future__ import annotations

from pathlib import Path
import importlib
import json
import shutil
import subprocess
import sys
import tempfile

def _find_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        if (parent / 'mugenforge').is_dir() and (parent / 'requirements.txt').exists():
            return parent
    return here.parents[1]

ROOT = _find_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def run(cmd: list[str]) -> None:
    print('RUN:', ' '.join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> int:
    run([sys.executable, '-m', 'compileall', '-q', 'mugenforge'])
    import mugenforge
    from mugenforge.app import APP_TITLE
    print('VERSION', mugenforge.__version__)
    print('APP_TITLE', APP_TITLE)
    expected_modules = [
        'mugenforge.maintenance_core', 'mugenforge.handoff_core', 'mugenforge.operator_console', 'mugenforge.evidence_core', 'mugenforge.authority_core',
        'mugenforge.runtime_lab', 'mugenforge.binary_maturity', 'mugenforge.forge_timeline',
        'mugenforge.visual_forge', 'mugenforge.sff_codec', 'mugenforge.snd_codec',
    ]
    for name in expected_modules:
        importlib.import_module(name)
        print('IMPORT_OK', name)
    from mugenforge.parsers import make_new_character
    from mugenforge.maintenance_core import run_maintenance_core_pass
    with tempfile.TemporaryDirectory(prefix='mugenforge_smoke_') as td:
        project = make_new_character(Path(td), 'SmokeHero')
        result = run_maintenance_core_pass(project)
        print(result.to_text())
        assert (project / 'maintenance_core' / 'MAINTAINER_START_HERE.md').exists()
        assert (project / 'maintenance_core' / 'HANDOFF_FOR_NEXT_CHAT.md').exists()
    print('SMOKE_PASS')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
