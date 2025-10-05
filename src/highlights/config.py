"""Configuration helpers for the highlight synchroniser."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class SyncConfig:
    """Holds configuration for syncing highlights."""

    clippings_path: Optional[Path] = None
    kindle_export_csv: Optional[Path] = None
    vault_root: Path = Path("./vault")
    vault_subdir: str = "Kindle Highlights"
    dry_run: bool = False
    highlight_heading_template: str = "Location {location}"

    @classmethod
    def from_mapping(cls, data: Dict[str, Any]) -> "SyncConfig":
        kwargs: Dict[str, Any] = {}
        if "clippings_path" in data and data["clippings_path"]:
            kwargs["clippings_path"] = Path(data["clippings_path"])
        if "kindle_export_csv" in data and data["kindle_export_csv"]:
            kwargs["kindle_export_csv"] = Path(data["kindle_export_csv"])
        if "vault_root" in data and data["vault_root"]:
            kwargs["vault_root"] = Path(data["vault_root"])
        if "vault_subdir" in data and data["vault_subdir"]:
            kwargs["vault_subdir"] = str(data["vault_subdir"])
        if "dry_run" in data:
            kwargs["dry_run"] = bool(data["dry_run"])
        if "highlight_heading_template" in data and data["highlight_heading_template"]:
            kwargs["highlight_heading_template"] = str(data["highlight_heading_template"])
        return cls(**kwargs)


def load_config(path: Optional[Path]) -> Dict[str, Any]:
    """Load a JSON configuration file if provided."""

    if path is None:
        return {}
    with path.expanduser().resolve().open("r", encoding="utf-8") as handle:
        return json.load(handle)
