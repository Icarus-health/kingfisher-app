#!/usr/bin/env python3
"""Read a local transcript export; print segments without importing or uploading."""
import argparse
import json
from pathlib import Path
import sys
import importlib.util


def _load_parser():
    parser_path = Path(__file__).resolve().parents[1] / "sidecar" / "icarus_memory" / "transcript_import.py"
    spec = importlib.util.spec_from_file_location("transcript_import", parser_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load transcript parser module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.parse_transcript


parse_transcript = _load_parser()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--format", choices=("txt", "srt", "vtt"))
    args = parser.parse_args()
    try:
        # Bound the read before decoding, including a possible UTF-8 BOM.
        with args.file.open("rb") as source:
            data = source.read(8_000_004)
        if len(data) > 8_000_003:
            raise ValueError("Transcript file is too large.")
        segments = parse_transcript(data.decode("utf-8-sig"), args.format or args.file.suffix.lstrip(".").lower())
    except (OSError, UnicodeError, ValueError) as exc:
        parser.exit(2, f"Cannot preview transcript: {exc}\n")
    print(json.dumps({"segments": segments}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
