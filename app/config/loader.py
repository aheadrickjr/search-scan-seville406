"""Loaders for the editable YAML config files (queries, domain lists)."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel


class DomainConfig(BaseModel):
    pir_domains: list[str] = []
    franke_domains: list[str] = []
    ota_domains: list[str] = []


def load_queries(path: Path) -> list[str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    queries = data.get("queries", [])
    if not queries:
        raise ValueError(f"No queries found in {path}")
    return list(queries)


def load_domains(path: Path) -> DomainConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return DomainConfig(**data)
