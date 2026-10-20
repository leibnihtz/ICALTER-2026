"""ICALTER v3 — dataset público (Bloque 3).

IDs sintéticos de estudiante, sesión, run, pregunta y concepto; sin timestamps
exactos ni texto libre. Escribe data/public_v3/leibtimeter_public_v3.csv y
outputs/v3/public_privacy_checks.json. La validación de modelos (Δ = 0) la hace
16_v3_validate_public.R.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "outputs" / "validation" / "analysis_v3.csv"
PUBLIC_DIR = ROOT / "data" / "public_v3"
PUBLIC = PUBLIC_DIR / "leibtimeter_public_v3.csv"
CHECKS = ROOT / "outputs" / "v3" / "public_privacy_checks.json"

PUBLIC_COLUMNS = ["student_id", "course", "term", "session_id", "run_id", "question_id", "concept_id",
                  "question_type", "response_time_seconds", "is_correct", "key_excluded"]


def synthetic(values: pd.Series, prefix: str, width: int) -> dict:
    # Orden por el hash salado: no conserva orden de llegada ni de registro.
    return {v: f"{prefix}_{i:0{width}d}" for i, v in enumerate(sorted(values.dropna().unique()), start=1)}


def main() -> None:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    priv = pd.read_csv(PRIVATE)
    maps = {
        "student_id": synthetic(priv["student_id"], "student", 3),
        "session_id": synthetic(priv["session_id"], "session", 3),
        "run_id": synthetic(priv["run_id"], "run", 3),
        "question_id": synthetic(priv["question_id"], "question", 3),
        "concept": synthetic(priv["concept"], "concept", 2),
    }
    pub = pd.DataFrame({
        "student_id": priv["student_id"].map(maps["student_id"]),
        "course": priv["course"], "term": priv["term"],
        "session_id": priv["session_id"].map(maps["session_id"]),
        "run_id": priv["run_id"].map(maps["run_id"]),
        "question_id": priv["question_id"].map(maps["question_id"]),
        "concept_id": priv["concept"].map(maps["concept"]),
        "question_type": priv["question_type"],
        "response_time_seconds": priv["response_time_seconds"],
        "is_correct": priv["correct"].astype(int),
        "key_excluded": priv["key_excluded"].astype(bool).astype(int),
    })[PUBLIC_COLUMNS]
    # Mismo orden canónico que analysis_v3.csv (estudiante, run): necesario para Δ = 0 exacto.
    pub = pub.sort_values(["student_id", "run_id"]).reset_index(drop=True)
    if pub.drop(columns="concept_id").isna().any().any():
        raise ValueError("public dataset has missing values")
    pub.to_csv(PUBLIC, index=False, float_format="%.6f")

    text = PUBLIC.read_text(encoding="utf-8")
    checks = {
        "rows": len(pub), "columns": list(pub.columns),
        "allowed_columns_only": list(pub.columns) == PUBLIC_COLUMNS,
        "md5_like_values_absent": re.search(r"\b[0-9a-f]{32}\b", text) is None,
        "uuid_like_values_absent": re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-", text) is None,
        "email_like_values_absent": "@" not in text,
        "ip_like_values_absent": re.search(r"\b\d{1,3}(\.\d{1,3}){3}\b", text) is None,
        "timestamps_absent": re.search(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:", text) is None,
        "concept_tags_absent": not any(":" in str(c) for c in pub["concept_id"].dropna().unique()),
    }
    checks["all_passed"] = all(v for k, v in checks.items() if k.endswith(("_absent", "_only")))
    CHECKS.write_text(json.dumps(checks, indent=2), encoding="utf-8")
    print(json.dumps(checks, indent=1))


if __name__ == "__main__":
    main()
