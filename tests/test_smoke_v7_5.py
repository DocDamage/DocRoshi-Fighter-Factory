from __future__ import annotations

import compileall
import importlib
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class MugenForgeSmokeTests(unittest.TestCase):
    def test_compile_and_import_core_modules(self):
        self.assertTrue(compileall.compile_dir(str(ROOT / 'mugenforge'), quiet=1))

        import mugenforge
        from mugenforge.app import APP_TITLE

        self.assertEqual(mugenforge.__version__, '7.5.0')
        self.assertEqual(APP_TITLE, 'MugenForge Studio 7.5 Continuity Core')

        for name in [
            'mugenforge.handoff_core',
            'mugenforge.operator_console',
            'mugenforge.maintenance_core',
            'mugenforge.evidence_core',
            'mugenforge.authority_core',
            'mugenforge.runtime_lab',
            'mugenforge.binary_maturity',
            'mugenforge.forge_timeline',
            'mugenforge.ui_tabs.authority',
            'mugenforge.ui_tabs.base',
            'mugenforge.ui_tabs.binary',
            'mugenforge.ui_tabs.closure_evidence',
            'mugenforge.ui_tabs.continuity',
            'mugenforge.ui_tabs.creator_hub',
            'mugenforge.ui_tabs.forge_workspaces',
            'mugenforge.ui_tabs.gap_closer',
            'mugenforge.ui_tabs.image_factory',
            'mugenforge.ui_tabs.palette',
            'mugenforge.ui_tabs.plus_workspaces',
            'mugenforge.ui_tabs.rescue_lab',
            'mugenforge.ui_tabs.runtime_lab',
            'mugenforge.ui_tabs.sff2_bridge',
        ]:
            with self.subTest(module=name):
                importlib.import_module(name)

    def test_continuity_backends_write_expected_artifacts(self):
        from mugenforge.handoff_core import write_context_digest, write_package_inventory, write_regression_harness
        from mugenforge.operator_console import write_next_chat_handoff, write_operator_dashboard, write_operator_roadmap
        from mugenforge.parsers import make_new_character

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

            self.assertTrue(all(hasattr(result, 'warnings') for result in results))
            self.assertTrue((char / 'handoff_core' / 'digest' / 'CONTEXT_DIGEST.md').exists())
            self.assertTrue((char / 'handoff_core' / 'inventory' / 'PACKAGE_INVENTORY.md').exists())
            self.assertTrue((char / 'operator_console' / 'OPERATOR_DASHBOARD.md').exists())
            self.assertTrue((char / 'operator_console' / 'NEXT_CHAT_HANDOFF.md').exists())

    def test_continuity_tabs_build_and_preserve_callbacks(self):
        import tkinter as tk

        from mugenforge.app import MugenForgeApp

        try:
            app = MugenForgeApp()
        except tk.TclError as exc:
            raise unittest.SkipTest(f'Tk display unavailable: {exc}') from exc

        try:
            tabs = [app.notebook.tab(tab_id, 'text') for tab_id in app.notebook.tabs()]
            selected = app.notebook.tab(app.notebook.select(), 'text')

            self.assertIn('Operator Console', tabs)
            self.assertIn('Maintenance Core', tabs)
            self.assertIn('Handoff Core', tabs)
            self.assertIn('Binary Core', tabs)
            self.assertIn('Binary Deep', tabs)
            self.assertIn('Binary Maturity', tabs)
            self.assertIn('Runtime Lab', tabs)
            self.assertIn('Gap Closer', tabs)
            self.assertIn('Authority Core', tabs)
            self.assertIn('Authority Lab', tabs)
            self.assertIn('Closure Lab', tabs)
            self.assertIn('Evidence Core', tabs)
            self.assertIn('Creator Hub', tabs)
            self.assertIn('SFF2 Bridge', tabs)
            self.assertIn('Rescue Lab', tabs)
            self.assertIn('Image Factory', tabs)
            self.assertIn('Palettes', tabs)
            self.assertIn('Studio Plus', tabs)
            self.assertIn('Factory+', tabs)
            self.assertIn('Forge+ Doctor', tabs)
            self.assertIn('Forge Beyond', tabs)
            self.assertIn('Forge Polish', tabs)
            self.assertIn('Forge Timeline', tabs)
            self.assertEqual(selected, 'Operator Console')
            self.assertTrue(callable(getattr(app, 'operator_console_one_click_ui', None)))
            self.assertTrue(callable(getattr(app, 'maintenance_core_one_click_ui', None)))
            self.assertTrue(callable(getattr(app, 'handoff_core_one_click_ui', None)))
            self.assertTrue(callable(getattr(app, 'binary_core_one_click_ui', None)))
            self.assertTrue(callable(getattr(app, 'binary_deep_one_click_ui', None)))
            self.assertTrue(callable(getattr(app, 'binary_maturity_one_click_ui', None)))
            self.assertTrue(callable(getattr(app, 'runtime_lab_one_click_ui', None)))
            self.assertTrue(callable(getattr(app, 'gap_closer_one_click_ui', None)))
            self.assertTrue(callable(getattr(app, 'authority_core_one_click_ui', None)))
            self.assertTrue(callable(getattr(app, 'authority_lab_one_click_ui', None)))
            self.assertTrue(callable(getattr(app, 'closure_lab_one_click_ui', None)))
            self.assertTrue(callable(getattr(app, 'evidence_core_one_click_ui', None)))
            self.assertTrue(callable(getattr(app, 'creator_hub_one_click_ui', None)))
            self.assertTrue(callable(getattr(app, 'sff2_bridge_write_project_ui', None)))
            self.assertTrue(callable(getattr(app, 'rescue_lab_one_click_ui', None)))
            self.assertTrue(callable(getattr(app, 'forge_beyond_one_click_ui', None)))
            self.assertTrue(callable(getattr(app, 'forge_polish_one_click_ui', None)))
            self.assertTrue(callable(getattr(app, 'forge_timeline_one_click_ui', None)))
        finally:
            app.destroy()


if __name__ == '__main__':
    unittest.main()
