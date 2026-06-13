You are continuing development/testing for a MugenForge project using **MugenForge Studio v7.5.0 Operator Console**.

Project folder to open:

```text
.
```

Run the app with:

```bash
python -m mugenforge.app
```

Start in **Operator Console**. First open `operator_console/OPERATOR_DASHBOARD.md`, then refresh **One-Click Operator Pass**. Use the phase table below to decide whether to work in Forge Timeline, Binary Maturity, Runtime Lab, Authority Lab, or Evidence Core.

Current state summary:

- Operator score: 44/100
- Blocker count: 6
- AIR actions: 0
- StateDefs: 0
- Commands: 0
- HitDefs: 0
- SFF: missing
- SND: missing

Phase table:

| phase | status | reason | next_action |
| --- | --- | --- | --- |
| Project skeleton | needs work | Missing: .def, .air, .cmd, .cns, .sff, .snd | Run Project Home / Beginner Wizard or Auto Setup if base files are missing. |
| Animation coverage | pass | 0 AIR actions, 0 common actions missing. | Use Factory+ Required Animation Repair or Visual Timeline to fill/replace placeholder actions. |
| Move logic | needs work | 0 StateDefs, 0 commands, 0 HitDefs. | Use Move Composer 2.0 / Forge Timeline to author and tune moves. |
| State routing | pass | No missing numeric ChangeState/SelfState targets found. | Use State Graph / Authority Lab to inspect and retarget broken transitions. |
| Sprites / SFF | needs work | No SFF file detected. | Use Binary Maturity for existing SFF2, or Sheet Import / SFF2 Bridge for source images. |
| Sounds / SND | needs work | No SND file detected. | Use Sound Cue Editor, Binary Core SND sheets, or source WAV rebuild workflow. |
| Runtime evidence | not started | No runtime/evidence artifacts found yet. | Run Runtime Lab or Evidence Core with your local M.U.G.E.N/IKEMEN executable. |
| Release packaging | not started | No release/export artifacts found yet. | Run Release ZIP / Evidence Bundle / Operator Context Bundle near ship time. |

Clean-room guardrails:

- Do not use or copy Fighter Factory / VirtualTek source, assets, or proprietary logic.
- Keep binary work honest; unsupported/corrupt/custom binaries should be triaged and preserved, not guessed.
- Candidate builds and mutation flows should write backups and verification reports before install.
- Runtime authority comes from the user-configured external M.U.G.E.N/IKEMEN executable and collected evidence.

Suggested next release direction:

1. Keep improving Operator Console as the front door so beginners do not have to understand all historical tabs.
2. Add real project corpus tests for SFF2/SND variants and keep unsupported cases visible.
3. Continue turning sheet/report workflows into direct visual canvas workflows, especially timeline, graph, palettes, and stage.
4. Build installer/distribution polish only after the evidence/corpus loop is stable.
