from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from pipeline.config import ensure_parent_dir


def append_jsonl(path: str | Path, row: dict[str, Any]) -> None:
    ensure_parent_dir(path)
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    ensure_parent_dir(path)
    with Path(path).open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def iter_jsonl(path: str | Path) -> Iterator[dict[str, Any]]:
    jsonl_path = Path(path)
    if not jsonl_path.exists():
        return

    with jsonl_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def truncate_jsonl(path: str | Path) -> None:
    ensure_parent_dir(path)
    Path(path).write_text("", encoding="utf-8")
