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
            'mugenforge.app_mixins',
            'mugenforge.app_state',
            'mugenforge.artifact_io',
            'mugenforge.binary_results',
            'mugenforge.handoff_core',
            'mugenforge.operator_console',
            'mugenforge.maintenance_core',
            'mugenforge.evidence_core',
            'mugenforge.authority_core',
            'mugenforge.runtime_lab',
            'mugenforge.binary_maturity',
            'mugenforge.forge_timeline',
            'mugenforge.ui_actions.air_editor',
            'mugenforge.ui_actions.asset_workspaces',
            'mugenforge.ui_actions.code_authoring',
            'mugenforge.ui_actions.creator_os',
            'mugenforge.ui_actions.creator_suite',
            'mugenforge.ui_actions.factory_max',
            'mugenforge.ui_actions.factory_plus',
            'mugenforge.ui_actions.factory_ultra',
            'mugenforge.ui_actions.feature_bank',
            'mugenforge.ui_actions.image_factory',
            'mugenforge.ui_actions.palette',
            'mugenforge.ui_actions.plus_workspaces',
            'mugenforge.ui_actions.project_core',
            'mugenforge.ui_actions.quality_lab',
            'mugenforge.ui_actions.sound_pipeline',
            'mugenforge.ui_actions.sprite_pipeline',
            'mugenforge.ui_actions.visual_forge',
            'mugenforge.ui_tabs.app_builders',
            'mugenforge.ui_tabs.asset_workspaces',
            'mugenforge.ui_tabs.authority',
            'mugenforge.ui_tabs.base',
            'mugenforge.ui_tabs.binary',
            'mugenforge.ui_tabs.closure_evidence',
            'mugenforge.ui_tabs.continuity',
            'mugenforge.ui_tabs.core_builders',
            'mugenforge.ui_tabs.creator_factory_tabs',
            'mugenforge.ui_tabs.creator_hub',
            'mugenforge.ui_tabs.forge_workspaces',
            'mugenforge.ui_tabs.gap_closer',
            'mugenforge.ui_tabs.image_factory',
            'mugenforge.ui_tabs.palette',
            'mugenforge.ui_tabs.plus_workspaces',
            'mugenforge.ui_tabs.rescue_lab',
            'mugenforge.ui_tabs.runtime_lab',
            'mugenforge.ui_tabs.sff2_bridge',
            'mugenforge.ui_tabs.tab_registry',
            'mugenforge.ui_tabs.visual_forge_tabs',
        ]:
            with self.subTest(module=name):
                importlib.import_module(name)

    def test_feature_tab_registry_matches_builders(self):
        from mugenforge.ui_tabs.app_builders import AppTabBuilders
        from mugenforge.ui_tabs.tab_registry import (
            FEATURE_TAB_BUILDERS,
            FEATURE_TAB_LABELS,
            FEATURE_TAB_ROLES,
            FEATURE_TABS,
            WORKSPACE_ROLE_CHOICES,
            WORKSPACE_ROLES,
        )

        builders = [tab.builder for tab in FEATURE_TABS]
        labels = [tab.label for tab in FEATURE_TABS]
        roles = {tab.role for tab in FEATURE_TABS}

        self.assertEqual(tuple(builders), FEATURE_TAB_BUILDERS)
        self.assertEqual(tuple(labels), FEATURE_TAB_LABELS)
        self.assertEqual({tab.label: tab.role for tab in FEATURE_TABS}, FEATURE_TAB_ROLES)
        self.assertEqual(WORKSPACE_ROLE_CHOICES, ('All', *WORKSPACE_ROLES))
        self.assertEqual(len(builders), len(set(builders)))
        self.assertEqual(len(labels), len(set(labels)))
        self.assertTrue(roles.issubset(set(WORKSPACE_ROLES)))

        for builder in builders:
            with self.subTest(builder=builder):
                self.assertTrue(hasattr(AppTabBuilders, builder))

    def test_binary_result_model_stays_reexported(self):
        from mugenforge.binary_core import BinaryCoreResult as ReexportedBinaryCoreResult
        from mugenforge.binary_results import BinaryCoreResult

        self.assertIs(ReexportedBinaryCoreResult, BinaryCoreResult)

        result = BinaryCoreResult('Binary smoke')
        result.add_note('ready')
        result.add_note('ready')
        result.add_warning('check corpus')

        text = result.to_text()
        self.assertIn('Binary smoke', text)
        self.assertEqual(text.count('- ready'), 1)
        self.assertIn('- check corpus', text)

    def test_artifact_io_records_outputs(self):
        from mugenforge.artifact_io import (
            backup_file,
            rel_path,
            sha256_file,
            write_csv_artifact,
            write_json_artifact,
            write_text_artifact,
        )
        from mugenforge.binary_results import BinaryCoreResult

        with tempfile.TemporaryDirectory(prefix='mf_artifact_io_') as tmp:
            root = Path(tmp)
            result = BinaryCoreResult('Artifact smoke')

            note = write_text_artifact(root / 'out' / 'note.txt', 'hello', result, root, changed=True)
            data = write_json_artifact(root / 'out' / 'data.json', {'ok': True}, result, root)
            sheet = write_csv_artifact(root / 'out' / 'rows.csv', [{'name': 'alpha'}], ['name'], result, root)
            backup = backup_file(note, 'test')

            self.assertEqual(note.read_text(encoding='utf-8'), 'hello\n')
            self.assertIn('out/note.txt', result.changed_files)
            self.assertIn('out/data.json', result.created_files)
            self.assertIn('out/rows.csv', result.created_files)
            self.assertEqual(rel_path(root, sheet), 'out/rows.csv')
            self.assertEqual(sha256_file(note), 'cd2eca3535741f27a8ae40c31b0c41d4057a7a7b912b33b9aed86485d1c84676')
            self.assertIsNotNone(backup)
            self.assertTrue(backup.exists())
            self.assertIn('.bak_test_', backup.name)

            write_text_artifact(data, 'rewritten json path as text', result, root, track_existing=True)
            self.assertIn('out/data.json', result.changed_files)

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
            self.assertIn('Feature Bank', tabs)
            self.assertIn('Factory Max', tabs)
            self.assertIn('Factory Ultra', tabs)
            self.assertIn('Creator OS', tabs)
            self.assertIn('Quality Lab', tabs)
            self.assertIn('Creator Suite', tabs)
            self.assertIn('Creator Hub', tabs)
            self.assertIn('SFF2 Bridge', tabs)
            self.assertIn('Rescue Lab', tabs)
            self.assertIn('Image Factory', tabs)
            self.assertIn('Palettes', tabs)
            self.assertIn('Studio Plus', tabs)
            self.assertIn('Factory+', tabs)
            self.assertIn('Forge+ Doctor', tabs)
            self.assertIn('Sprite Lab', tabs)
            self.assertIn('Stage Builder', tabs)
            self.assertIn('Run / Test', tabs)
            self.assertIn('Project Home', tabs)
            self.assertIn('Visual Timeline', tabs)
            self.assertIn('Offset / Axis', tabs)
            self.assertIn('Sound Cue Editor', tabs)
            self.assertIn('Move Composer 2.0', tabs)
            self.assertIn('Migration Wizard', tabs)
            self.assertIn('Training Debug', tabs)
            self.assertIn('Templates / Plugins', tabs)
            self.assertIn('Backups / Logs', tabs)
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
            self.assertEqual(app.workspace_summary_var.get(), '41 feature tabs')
            app.workspace_role_var.set('Visual')
            app.apply_workspace_role()
            self.assertEqual(app.notebook.tab(app.feature_tab_ids_by_label['Visual Timeline'], 'state'), 'normal')
            self.assertEqual(app.notebook.tab(app.feature_tab_ids_by_label['Operator Console'], 'state'), 'hidden')
            self.assertEqual(app.workspace_summary_var.get(), '11 Visual tabs')
            app.workspace_role_var.set('All')
            app.apply_workspace_role()
            self.assertEqual(app.notebook.tab(app.feature_tab_ids_by_label['Operator Console'], 'state'), 'normal')
            self.assertEqual(app.notebook.tab(app.feature_tab_ids_by_label['Handoff Core'], 'state'), 'normal')
            self.assertEqual(app.workspace_summary_var.get(), '41 feature tabs')
        finally:
            app.destroy()


if __name__ == '__main__':
    unittest.main()
