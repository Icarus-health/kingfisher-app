# Pilot timezone assertion verification

Changed only `scripts/test_probe_mistral_memory_pilot.py`: imported `datetime` and compared the parsed actual and expected aware timestamps with `datetime.fromisoformat`.

Command (separate process, `TZ=UTC`):
```sh
TZ=UTC PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts:. /private/tmp/kf-core-20261104-env/bin/python -m pytest -q -p no:cacheprovider scripts/test_probe_mistral_memory_pilot.py::test_default_cli_previews_exact_sources_without_credentials_network_or_classification
```
Output: `. [100%]` — `1 passed in 1.20s` (exit 0).

Command (separate process, `TZ=Europe/Berlin`):
```sh
TZ=Europe/Berlin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts:. /private/tmp/kf-core-20261104-env/bin/python -m pytest -q -p no:cacheprovider scripts/test_probe_mistral_memory_pilot.py::test_default_cli_previews_exact_sources_without_credentials_network_or_classification
```
Output: `. [100%]` — `1 passed in 1.06s` (exit 0).

Final SHA-256 of `scripts/test_probe_mistral_memory_pilot.py`: `ba33289bcedf61754b9072f71c9f57ebc90c784bae57ccdd13bb7b0293401fdf`.
