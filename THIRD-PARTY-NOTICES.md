# Third-party notices

Kingfisher itself is licensed under the Apache License 2.0 (see `LICENSE`). It ships the following third-party material:

| Material | Where | License | License text |
|---|---|---|---|
| Inter typeface | `design-source/07_Coding_Package/Fonts/Inter-*.ttf` (also bundled into the UI build) | SIL Open Font License 1.1 | `design-source/07_Coding_Package/Fonts/Inter-OFL.txt` |
| Cormorant Garamond typeface | `design-source/07_Coding_Package/Fonts/CormorantGaramond-*.ttf` | SIL Open Font License 1.1 | `design-source/07_Coding_Package/Fonts/CormorantGaramond-OFL.txt` |
| Lucide icons (adapted) | `design-source/02_Icons/` | ISC License | `design-source/02_Icons/LUCIDE-LICENSE.txt` |
| python-dateutil (calendar recurrence rules) | Python dependency of the sidecar (`sidecar/pyproject.toml`), installed into the container image; used by `sidecar/icarus_memory/connectors/calendar.py` | Apache License 2.0 and BSD 3-Clause License (dual) | `LICENSE` in the installed package (`python_dateutil-*.dist-info/LICENSE`) |
| six (dependency of python-dateutil) | installed together with python-dateutil | MIT License | `LICENSE` in the installed package (`six-*.dist-info/LICENSE`) |

Images under `design-source/01_Brand` and `03_Media` were generated for this project (see `docs/release/ASSET-RELEASE-2026-09-27.md`). Product names and logos of third parties shown in design mockups belong to their owners and are used only to illustrate integrations.
