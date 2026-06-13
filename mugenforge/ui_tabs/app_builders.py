from __future__ import annotations

from .asset_workspaces import RunTestTab, SpriteLabTab, StageBuilderTab
from .authority import AuthorityCoreTab, AuthorityLabTab
from .binary import BinaryWorkspaceTabs
from .closure_evidence import ClosureLabTab, EvidenceCoreTab
from .continuity import HandoffCoreTab, MaintenanceCoreTab, OperatorConsoleTab
from .creator_factory_tabs import AutoBuilderTab, CreatorOSTab, CreatorSuiteTab, FactoryMaxTab, FactoryUltraTab, QualityLabTab
from .creator_hub import CreatorHubTab
from .forge_workspaces import ForgeBeyondTab, ForgePolishTab, ForgeTimelineTab
from .gap_closer import GapCloserTab
from .image_factory import ImageFactoryTab
from .palette import PaletteTab
from .plus_workspaces import FactoryPlusTab, ForgePlusTab, StudioPlusTab
from .rescue_lab import RescueLabTab
from .runtime_lab import RuntimeLabTab
from .sff2_bridge import Sff2BridgeTab
from .visual_forge_tabs import (
    BackupLogTab,
    MigrationWizardTab,
    MoveComposer2Tab,
    PluginTemplateTab,
    SoundCueEditorTab,
    SpriteOffsetAxisTab,
    TrainingDebugTab,
    VisualForgeHomeTab,
    VisualTimelineTab,
)


class AppTabBuilders:
    def _build_auto_builder_tab(self):
        self.auto_builder_tab = AutoBuilderTab(self)

    def _build_factory_max_tab(self):
        self.factory_max_tab = FactoryMaxTab(self)

    def _build_creator_os_tab(self):
        self.creator_os_tab = CreatorOSTab(self)

    def _build_factory_ultra_tab(self):
        self.factory_ultra_tab = FactoryUltraTab(self)

    def _build_quality_lab_tab(self):
        self.quality_lab_tab = QualityLabTab(self)

    def _build_creator_suite_tab(self):
        self.creator_suite_tab = CreatorSuiteTab(self)

    def _build_creator_hub_tab(self):
        self.creator_hub_tab = CreatorHubTab(self)

    def _build_sff2_bridge_tab(self):
        self.sff2_bridge_tab = Sff2BridgeTab(self)

    def _build_rescue_lab_tab(self):
        self.rescue_lab_tab = RescueLabTab(self)

    def _build_image_factory_tab(self):
        self.image_factory_tab = ImageFactoryTab(self)

    def _build_palette_tab(self):
        self.palette_tab = PaletteTab(self)

    def _build_studio_plus_tab(self):
        self.studio_plus_tab = StudioPlusTab(self)

    def _build_factory_plus_tab(self):
        self.factory_plus_tab = FactoryPlusTab(self)

    def _build_forge_plus_tab(self):
        self.forge_plus_tab = ForgePlusTab(self)

    def _build_sprite_lab_tab(self):
        self.sprite_lab_tab = SpriteLabTab(self)

    def _build_stage_builder_tab(self):
        self.stage_builder_tab = StageBuilderTab(self)

    def _build_run_test_tab(self):
        self.run_test_tab = RunTestTab(self)


    # ------------------------------------------------------------------
    # Visual Forge v3.5 beginner-first workflow tabs
    # ------------------------------------------------------------------

    def _build_visual_forge_home_tab(self):
        self.visual_forge_home_tab = VisualForgeHomeTab(self)

    def _build_visual_timeline_editor_tab(self):
        self.visual_timeline_tab = VisualTimelineTab(self)

    def _build_sprite_offset_axis_tab(self):
        self.sprite_offset_axis_tab = SpriteOffsetAxisTab(self)

    def _build_sound_cue_editor_tab(self):
        self.sound_cue_editor_tab = SoundCueEditorTab(self)

    def _build_move_composer2_tab(self):
        self.move_composer2_tab = MoveComposer2Tab(self)

    def _build_migration_wizard_tab(self):
        self.migration_wizard_tab = MigrationWizardTab(self)

    def _build_training_debug_tab(self):
        self.training_debug_tab = TrainingDebugTab(self)

    def _build_plugin_template_tab(self):
        self.plugin_template_tab = PluginTemplateTab(self)

    def _build_backup_log_tab(self):
        self.backup_log_tab = BackupLogTab(self)

    def _build_forge_beyond_tab(self):
        self.forge_beyond_tab = ForgeBeyondTab(self)

    def _build_forge_polish_tab(self):
        self.forge_polish_tab = ForgePolishTab(self)

    def _build_forge_timeline_tab(self):
        self.forge_timeline_tab = ForgeTimelineTab(self)

    def _build_binary_core_tab(self):
        if not hasattr(self, 'binary_workspace_tab'):
            self.binary_workspace_tab = BinaryWorkspaceTabs(self)

    def _build_binary_deep_tab(self):
        if not hasattr(self, 'binary_workspace_tab'):
            self.binary_workspace_tab = BinaryWorkspaceTabs(self)

    def _build_binary_maturity_tab(self):
        if not hasattr(self, 'binary_workspace_tab'):
            self.binary_workspace_tab = BinaryWorkspaceTabs(self)

    def _build_runtime_lab_tab(self):
        self.runtime_lab_tab = RuntimeLabTab(self)

    def _build_gap_closer_tab(self):
        self.gap_closer_tab = GapCloserTab(self)

    def _build_authority_core_tab(self):
        self.authority_core_tab = AuthorityCoreTab(self)

    def _build_authority_lab_tab(self):
        self.authority_lab_tab = AuthorityLabTab(self)

    def _build_closure_lab_tab(self):
        self.closure_lab_tab = ClosureLabTab(self)

    def _build_evidence_core_tab(self):
        self.evidence_core_tab = EvidenceCoreTab(self)

    def _build_handoff_core_tab(self):
        self.handoff_core_tab = HandoffCoreTab(self)

    def _build_operator_console_tab(self):
        self.operator_console_tab = OperatorConsoleTab(self)

    def _build_maintenance_core_tab(self):
        self.maintenance_core_tab = MaintenanceCoreTab(self)
