# UI Tab Inventory

Generated: 2026-06-13T19:18:18

Tabs detected: 54
Tab builder methods detected: 42
Build calls detected: 40

| # | Tab | app.py line | Builder guess |
|---:|---|---:|---|
| 1 | Editor | 321 | `` |
| 2 | Analysis | 324 | `` |
| 3 | Code Map | 339 | `` |
| 4 | AIR Timeline | 349 | `` |
| 5 | CLSN Editor | 399 | `` |
| 6 | Sprites | 438 | `` |
| 7 | Sheet Import | 493 | `` |
| 8 | Sounds | 522 | `` |
| 9 | Binary / Preview | 525 | `` |
| 10 | Animation Player | 551 | `` |
| 11 | Code Assistant | 581 | `` |
| 12 | Move Wizard | 618 | `` |
| 13 | Feature Bank | 742 | `_build_auto_builder_tab` |
| 14 | Factory Max | 811 | `_build_factory_max_tab` |
| 15 | Factory Ultra | 878 | `_build_factory_ultra_tab` |
| 16 | Creator OS | 949 | `_build_creator_os_tab` |
| 17 | Factory Ultra | 1006 | `_build_factory_ultra_tab` |
| 18 | Quality Lab | 1066 | `_build_quality_lab_tab` |
| 19 | Creator Suite | 1198 | `_build_creator_suite_tab` |
| 20 | Creator Hub | 1342 | `_build_creator_hub_tab` |
| 21 | SFF2 Bridge | 1469 | `_build_sff2_bridge_tab` |
| 22 | Rescue Lab | 1642 | `_build_rescue_lab_tab` |
| 23 | Image Factory | 1742 | `_build_image_factory_tab` |
| 24 | Palettes | 1779 | `_build_palette_tab` |
| 25 | Studio Plus | 1862 | `_build_studio_plus_tab` |
| 26 | Factory+ | 1921 | `_build_factory_plus_tab` |
| 27 | Forge+ Doctor | 1964 | `_build_forge_plus_tab` |
| 28 | Sprite Lab | 2032 | `_build_sprite_lab_tab` |
| 29 | Stage Builder | 2070 | `_build_stage_builder_tab` |
| 30 | Run / Test | 2100 | `_build_run_test_tab` |
| 31 | Project Home | 2264 | `_build_visual_forge_home_tab` |
| 32 | Visual Timeline | 2404 | `_build_visual_timeline_editor_tab` |
| 33 | Offset / Axis | 2617 | `_build_sprite_offset_axis_tab` |
| 34 | Sound Cue Editor | 2766 | `_build_sound_cue_editor_tab` |
| 35 | Move Composer 2.0 | 2859 | `_build_move_composer2_tab` |
| 36 | Migration Wizard | 2924 | `_build_migration_wizard_tab` |
| 37 | Training Debug | 2970 | `_build_training_debug_tab` |
| 38 | Templates / Plugins | 3004 | `_build_plugin_template_tab` |
| 39 | Backups / Logs | 3056 | `_build_backup_log_tab` |
| 40 | Forge Beyond | 6333 | `_build_forge_beyond_tab` |
| 41 | Forge Polish | 6614 | `_build_forge_polish_tab` |
| 42 | Forge Timeline | 6952 | `_build_forge_timeline_tab` |
| 43 | Binary Core | 7232 | `_build_binary_core_tab` |
| 44 | Binary Deep | 7464 | `_build_binary_deep_tab` |
| 45 | Binary Maturity | 7655 | `_build_binary_maturity_tab` |
| 46 | Runtime Lab | 7833 | `_build_runtime_lab_tab` |
| 47 | Gap Closer | 8011 | `_build_gap_closer_tab` |
| 48 | Authority Core | 8240 | `_build_authority_core_tab` |
| 49 | Authority Lab | 8464 | `_build_authority_lab_tab` |
| 50 | Closure Lab | 8645 | `_build_closure_lab_tab` |
| 51 | Evidence Core | 8875 | `_build_evidence_core_tab` |
| 52 | Handoff Core | 9106 | `_build_handoff_core_tab` |
| 53 | Operator Console | 9210 | `_build_operator_console_tab` |
| 54 | Maintenance Core | 9336 | `_build_maintenance_core_tab` |

## Build call order

1. `_build_auto_builder_tab()` — app.py line 620
2. `_build_factory_plus_tab()` — app.py line 621
3. `_build_factory_max_tab()` — app.py line 622
4. `_build_factory_ultra_tab()` — app.py line 623
5. `_build_creator_os_tab()` — app.py line 624
6. `_build_creator_suite_tab()` — app.py line 625
7. `_build_creator_hub_tab()` — app.py line 626
8. `_build_rescue_lab_tab()` — app.py line 627
9. `_build_sff2_bridge_tab()` — app.py line 628
10. `_build_image_factory_tab()` — app.py line 629
11. `_build_palette_tab()` — app.py line 630
12. `_build_studio_plus_tab()` — app.py line 631
13. `_build_forge_plus_tab()` — app.py line 632
14. `_build_sprite_lab_tab()` — app.py line 633
15. `_build_stage_builder_tab()` — app.py line 634
16. `_build_run_test_tab()` — app.py line 635
17. `_build_visual_forge_home_tab()` — app.py line 636
18. `_build_visual_timeline_editor_tab()` — app.py line 637
19. `_build_sprite_offset_axis_tab()` — app.py line 638
20. `_build_sound_cue_editor_tab()` — app.py line 639
21. `_build_move_composer2_tab()` — app.py line 640
22. `_build_migration_wizard_tab()` — app.py line 641
23. `_build_training_debug_tab()` — app.py line 642
24. `_build_plugin_template_tab()` — app.py line 643
25. `_build_backup_log_tab()` — app.py line 644
26. `_build_forge_beyond_tab()` — app.py line 645
27. `_build_forge_polish_tab()` — app.py line 646
28. `_build_forge_timeline_tab()` — app.py line 647
29. `_build_binary_core_tab()` — app.py line 648
30. `_build_binary_deep_tab()` — app.py line 649
31. `_build_binary_maturity_tab()` — app.py line 650
32. `_build_closure_lab_tab()` — app.py line 651
33. `_build_gap_closer_tab()` — app.py line 652
34. `_build_authority_core_tab()` — app.py line 653
35. `_build_runtime_lab_tab()` — app.py line 654
36. `_build_authority_lab_tab()` — app.py line 655
37. `_build_evidence_core_tab()` — app.py line 656
38. `_build_maintenance_core_tab()` — app.py line 657
39. `_build_operator_console_tab()` — app.py line 658
40. `_build_handoff_core_tab()` — app.py line 659
