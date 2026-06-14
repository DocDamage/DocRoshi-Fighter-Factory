from __future__ import annotations

from pathlib import Path
from datetime import datetime
import json
import subprocess
import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cfg_path = Path(argv[0]) if argv else Path('runtime_validation_config.json')
    if not cfg_path.exists():
        print(f'Config not found: {cfg_path}', file=sys.stderr)
        return 2
    cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
    engine = str(cfg.get('engine_executable') or '').strip()
    if not engine:
        print('engine_executable is blank. Edit runtime_validation_config.json first.', file=sys.stderr)
        return 2
    command = [engine] + [str(x) for x in cfg.get('arguments', [])]
    cwd = str(cfg.get('working_directory') or cfg_path.parent)
    timeout = int(cfg.get('timeout_seconds') or 30)
    out_dir = cfg_path.parent / 'runtime_logs'
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = datetime.now().strftime('%Y%m%d_%H%M%S')
    try:
        proc = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        (out_dir / f'runtime_stdout_{tag}.txt').write_text(proc.stdout or '', encoding='utf-8', errors='replace')
        (out_dir / f'runtime_stderr_{tag}.txt').write_text(proc.stderr or '', encoding='utf-8', errors='replace')
        (out_dir / f'runtime_result_{tag}.json').write_text(json.dumps({
            'command': command,
            'cwd': cwd,
            'timeout_seconds': timeout,
            'returncode': proc.returncode,
            'stdout_file': f'runtime_stdout_{tag}.txt',
            'stderr_file': f'runtime_stderr_{tag}.txt',
        }, indent=2) + '\n', encoding='utf-8')
        print(f'Runtime command exited with {proc.returncode}. Logs written to {out_dir}')
        return proc.returncode
    except subprocess.TimeoutExpired as exc:
        (out_dir / f'runtime_timeout_{tag}.json').write_text(json.dumps({
            'command': command,
            'cwd': cwd,
            'timeout_seconds': timeout,
            'error': 'timeout',
            'stdout': exc.stdout,
            'stderr': exc.stderr,
        }, indent=2) + '\n', encoding='utf-8', errors='replace')
        print(f'Runtime command timed out after {timeout} seconds. Evidence written to {out_dir}', file=sys.stderr)
        return 124
    except Exception as exc:
        (out_dir / f'runtime_error_{tag}.json').write_text(json.dumps({
            'command': command,
            'cwd': cwd,
            'error': str(exc),
        }, indent=2) + '\n', encoding='utf-8')
        print(f'Runtime command failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
