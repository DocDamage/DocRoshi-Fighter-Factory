from __future__ import annotations

from .ui_actions.air_editor import AirEditorActions
from .ui_actions.asset_workspaces import AssetWorkspaceActions
from .ui_actions.code_authoring import CodeAuthoringActions
from .ui_actions.creator_os import CreatorOSActions
from .ui_actions.creator_suite import CreatorSuiteActions
from .ui_actions.factory_max import FactoryMaxActions
from .ui_actions.factory_plus import FactoryPlusActions
from .ui_actions.factory_ultra import FactoryUltraActions
from .ui_actions.feature_bank import FeatureBankActions
from .ui_actions.image_factory import ImageFactoryActions
from .ui_actions.palette import PaletteActions
from .ui_actions.plus_workspaces import PlusWorkspaceActions
from .ui_actions.project_core import ProjectCoreActions
from .ui_actions.quality_lab import QualityLabActions
from .ui_actions.sound_pipeline import SoundPipelineActions
from .ui_actions.sprite_pipeline import SpritePipelineActions
from .ui_actions.visual_forge import VisualForgeActions
from .ui_tabs.app_builders import AppTabBuilders


class AppBehaviorMixins(
    FeatureBankActions,
    CreatorOSActions,
    CreatorSuiteActions,
    AirEditorActions,
    AppTabBuilders,
    AssetWorkspaceActions,
    CodeAuthoringActions,
    FactoryMaxActions,
    FactoryPlusActions,
    FactoryUltraActions,
    ImageFactoryActions,
    PaletteActions,
    PlusWorkspaceActions,
    ProjectCoreActions,
    QualityLabActions,
    SoundPipelineActions,
    SpritePipelineActions,
    VisualForgeActions,
):
    pass
