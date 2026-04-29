from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from pipeline.config import AppConfig, ensure_parent_dir
from pipeline.export_jsonl import iter_jsonl


def _write_parquet(input_path: str | Path, output_path: str | Path) -> int:
    rows = list(iter_jsonl(input_path))
    ensure_parent_dir(output_path)
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, output_path)
    return len(rows)


def export_trace_parquet(config: AppConfig) -> dict[str, int]:
    accepted_count = _write_parquet(
        config.output.accepted_path,
        config.output.accepted_parquet_path,
    )
    rejected_count = _write_parquet(
        config.output.rejected_path,
        config.output.rejected_parquet_path,
    )
    return {
        "accepted_rows": accepted_count,
        "rejected_rows": rejected_count,
    }
