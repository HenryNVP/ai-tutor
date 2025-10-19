#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import URLError
from urllib.request import urlretrieve

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = PROJECT_ROOT / "data" / "sources.yaml"


def load_openstax_sources() -> Dict[str, Dict[str, Any]]:
    if not SOURCES_PATH.exists():
        raise FileNotFoundError(f"Metadata file not found: {SOURCES_PATH}")
    with SOURCES_PATH.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    entries = payload.get("sources", [])
    openstax_entries = {
        entry["id"]: entry
        for entry in entries
        if entry.get("organization", "").lower() == "openstax"
    }
    if not openstax_entries:
        raise RuntimeError("No OpenStax sources found in metadata file.")
    return openstax_entries


def download_textbook(entry: Dict[str, Any], destination_dir: Path, overwrite: bool = False) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    download_url = entry.get("download_url")
    if not download_url:
        raise ValueError(f"Source {entry['id']} is missing a download_url.")

    filename = Path(download_url).name or f"{entry['id']}.pdf"
    destination_path = destination_dir / filename

    if destination_path.exists() and not overwrite:
        return destination_path

    try:
        urlretrieve(download_url, destination_path)
    except URLError as exc:  # noqa: BLE001
        raise RuntimeError(f"Failed to download {download_url}: {exc}") from exc

    return destination_path


def ingest_with_system(document_dir: Path, config: Optional[Path], api_key: Optional[str]) -> Dict[str, Any]:
    from ai_tutor.system import TutorSystem

    system = TutorSystem.from_config(config, api_key=api_key)
    result = system.ingest_directory(document_dir)
    return {
        "documents": len(result.documents),
        "chunks": len(result.chunks),
        "skipped": [str(path) for path in result.skipped],
    }


def parse_args() -> argparse.Namespace:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Download OpenStax textbooks and ingest them into the AI Tutor corpus."
    )
    parser.add_argument(
        "--book-id",
        default="openstax_physics",
        help="Book ID from data/sources.yaml (default: openstax_physics).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "raw" / "openstax",
        help="Directory where downloaded files are stored.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional path to config YAML passed to TutorSystem.",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=os.getenv("GEMINI_API_KEY"),
        help="Optional API key for downstream LLM calls.",
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="Trigger ingestion with TutorSystem after download completes.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files when downloading.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    sources = load_openstax_sources()
    if args.book_id not in sources:
        print(f"Unknown book id '{args.book_id}'. Available ids:\n  - " + "\n  - ".join(sorted(sources)), file=sys.stderr)
        sys.exit(1)

    entry = sources[args.book_id]
    destination = download_textbook(entry, args.output_dir, overwrite=args.overwrite)

    payload: Dict[str, Any] = {
        "book_id": entry["id"],
        "title": entry["title"],
        "downloaded_to": str(destination),
        "license": entry.get("license"),
        "license_notes": entry.get("license_notes"),
    }

    if args.ingest:
        ingest_result = ingest_with_system(args.output_dir, args.config, args.api_key)
        payload["ingest"] = ingest_result

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
