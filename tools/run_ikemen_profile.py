from __future__ import annotations

from datetime import datetime
from pathlib import Path
import argparse
import json
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PROFILES = {
    "live": {
        "cwd": Path(r"C:\Users\dferr\tools\Ikemen-GO"),
        "exe": Path(r"C:\Users\dferr\tools\Ikemen-GO\Ikemen_GO.exe"),
        "stage": "stages/kfm.def",
    },
    "vpfg": {
        "cwd": Path(r"C:\Users\dferr\tools\Ikemen-GO-VPFG-2.6"),
        "exe": Path(r"C:\Users\dferr\tools\Ikemen-GO-VPFG-2.6\Ikemen_GO.exe"),
        "stage": "stages/VP_Training_Room.def",
    },
    "candidate": {
        "cwd": Path(r"C:\Users\dferr\tools\Ikemen-GO-live-vpfg-merge-candidate"),
        "exe": Path(r"C:\Users\dferr\tools\Ikemen-GO-live-vpfg-merge-candidate\Ikemen_GO.exe"),
        "stage": "stages/kfm.def",
    },
    "ikegen": {
        "cwd": Path(r"C:\Users\dferr\tools\Ikemen-GO-Ikemen-Generations"),
        "exe": Path(r"C:\Users\dferr\tools\Ikemen-GO-Ikemen-Generations\Ikemen_GO.exe"),
        "stage": "stages/TrainingGrid.def",
    },
    "swr": {
        "cwd": Path(r"C:\Users\dferr\tools\Ikemen-GO-SWR-Lifebar"),
        "exe": Path(r"C:\Users\dferr\tools\Ikemen-GO-SWR-Lifebar\Ikemen_GO.exe"),
        "stage": "stages/TrainingGrid.def",
    },
    "mbevo": {
        "cwd": Path(r"C:\Users\dferr\tools\Ikemen-GO-MBEVO"),
        "exe": Path(r"C:\Users\dferr\tools\Ikemen-GO-MBEVO\Ikemen_GO.exe"),
        "stage": "stages/TrainingGrid.def",
    },
}


def build_args(profile: str, p1: str, p2: str, stage: str, log: Path) -> list[str]:
    cfg = PROFILES[profile]
    return [
        str(cfg["exe"]),
        "-windowed",
        "-nosound",
        "-nojoy",
        "-log",
        str(log),
        "-p1",
        p1,
        "-p1.ai",
        "8",
        "-p2",
        p2,
        "-p2.ai",
        "8",
        "-s",
        stage,
        "-rounds",
        "1",
        "-time",
        "1",
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a short IKEMEN smoke profile.")
    parser.add_argument("profile", choices=sorted(PROFILES))
    parser.add_argument("--p1", default="kfm_zss")
    parser.add_argument("--p2", default="kfm_zss")
    parser.add_argument("--stage", default="")
    parser.add_argument("--timeout", type=int, default=75)
    args = parser.parse_args(argv)

    cfg = PROFILES[args.profile]
    stage = args.stage or str(cfg["stage"])
    outdir = ROOT / "evidence_core" / "runtime_runs" / "manual_profiles"
    outdir.mkdir(parents=True, exist_ok=True)
    tag = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    log = outdir / f"{args.profile}_{args.p1.replace('/', '_')}_vs_{args.p2.replace('/', '_')}_{tag}.log"
    command = build_args(args.profile, args.p1, args.p2, stage, log)

    try:
        proc = subprocess.run(
            command,
            cwd=str(cfg["cwd"]),
            capture_output=True,
            text=True,
            timeout=args.timeout,
        )
        result = {
            "profile": args.profile,
            "command": command,
            "cwd": str(cfg["cwd"]),
            "returncode": proc.returncode,
            "status": "pass" if proc.returncode == 0 else "fail",
            "log": str(log),
            "stdout_tail": (proc.stdout or "")[-3000:],
            "stderr_tail": (proc.stderr or "")[-3000:],
        }
    except subprocess.TimeoutExpired as exc:
        result = {
            "profile": args.profile,
            "command": command,
            "cwd": str(cfg["cwd"]),
            "status": "timeout",
            "timeout_seconds": args.timeout,
            "log": str(log),
            "stdout_tail": (exc.stdout or "")[-3000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-3000:] if isinstance(exc.stderr, str) else "",
        }

    result_path = outdir / f"{args.profile}_runtime_result_{tag}.json"
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "result": str(result_path)}, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
