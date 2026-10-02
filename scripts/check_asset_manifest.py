#!/usr/bin/env python3
"""Reject unapproved visual assets in the canonical Kingfisher frontend."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "design-source"
UI = ROOT / "app" / "kingfisher" / "src"
MANIFEST = DESIGN / "07_Coding_Package" / "KINGFISHER-ASSET-MANIFEST-v1.json"


def fail(message: str) -> None:
    print(f"asset-check: {message}", file=sys.stderr)
    raise SystemExit(1)


def required_files(manifest: dict) -> set[str]:
    """Der freigegebene Vertrag muss auch als vollständige Build-Kopie vorliegen."""
    brand = manifest["brand"]
    fonts = manifest["fonts"]
    media = manifest["media"]
    paths = set(manifest["screenReferences"].values())
    paths.update((brand["logoLight"], brand["logoDark"]))
    paths.update(brand["appIcons"].format(size=size) for size in brand["allowedAppIconSizes"])
    paths.update(f"{fonts['source']}/{name}" for name in (*fonts["display"], *fonts["ui"], fonts["stylesheet"]))
    paths.update(f"{media['source']}/{name}" for name in media["approved"])
    return paths


def check_required_files(manifest: dict, design: Path) -> None:
    missing = []
    for relative in sorted(required_files(manifest)):
        path = design / relative
        if not path.resolve().is_relative_to(design.resolve()):
            fail(f"Asset-Pfad liegt außerhalb der Designquelle: {relative}")
        if not path.is_file() or path.stat().st_size == 0:
            missing.append(relative)
    if missing:
        fail("freigegebene Build-Dateien fehlen oder sind leer:\n" + "\n".join(missing))


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    check_required_files(manifest, DESIGN)
    manifest_text = json.dumps(manifest, ensure_ascii=False)
    sources = "\n".join(path.read_text(encoding="utf-8") for path in UI.rglob("*") if path.is_file())

    mirror = manifest.get("driveMirror")
    if not isinstance(mirror, dict) or mirror.get("required") is not True:
        fail("verbindliche Google-Drive-Doppelablage fehlt im Manifest")
    for field in ("sourceOfRecord", "folderId", "repositoryRole", "rule", "releaseRule"):
        if not isinstance(mirror.get(field), str) or not mirror[field].strip():
            fail(f"Drive-Doppelablage unvollständig: {field}")

    banned = {
        "lucide": "fremdes Icon-Paket",
        "heroicons": "fremdes Icon-Paket",
        "fontawesome": "fremdes Icon-Paket",
        "unpkg.com": "CDN-Asset",
        "unsplash": "Stockbild",
        "placeholder.com": "Placeholder-Bild",
    }
    for needle, reason in banned.items():
        if needle.lower() in sources.lower():
            fail(f"{reason} gefunden: {needle}")

    if re.search(r"[\U0001F300-\U0001FAFF]", sources):
        fail("Emoji im Frontend gefunden")

    referenced_files = set(re.findall(r"[A-Za-z0-9_-]+(?:\.png|\.ttf)", sources))
    for name in sorted(referenced_files):
        if name not in manifest_text and not re.fullmatch(r"kingfisher-app-icon-(?:20|29|40|60|80|120|152|167|180|256|512|1024)\.png", name):
            fail(f"nicht manifestierte Datei referenziert: {name}")

    icon_names = set(re.findall(r'icon\("([a-z0-9-]+)"', sources))
    icon_names.update(re.findall(r'\["[^"\n]+",\s*"([a-z0-9-]+)"\]', sources))
    # Diese Werte kommen aus dem typisierten Morning-Briefing-Vertrag.
    icon_names.update({"folder", "mail", "message-circle", "brain", "file-text", "network", "circle-alert", "info"})
    approved_icons = set(manifest.get("icons", {}).get("approvedNames", []))
    for name in sorted(icon_names):
        if name not in approved_icons:
            fail(f"Icon nicht in Manifest-Allowlist: {name}")
        for variant in ("Filled", "Outline"):
            path = DESIGN / "02_Icons" / "Approved" / variant / f"{name}.svg"
            if not path.is_file():
                fail(f"Icon nicht in Approved vorhanden: {variant}/{name}.svg")

    visual_suffixes = {".png", ".svg", ".ttf", ".woff", ".woff2", ".jpg", ".jpeg", ".webp"}
    for path in UI.rglob("*"):
        if path.is_file() and path.suffix.lower() in visual_suffixes:
            fail(f"kopiertes oder neues Asset außerhalb der Designquelle: {path.relative_to(ROOT)}")

    print(f"asset-check: pass ({len(referenced_files)} Dateien, {len(icon_names)} Icons)")


if __name__ == "__main__":
    main()

