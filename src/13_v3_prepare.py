"""ICALTER v3 — dataset de análisis y descriptivos (B3, chequeo por run, bandas de RT).

Aplica ANALYSIS_PLAN_v3.md §2 sobre data/private_v3/q4_responses.csv y escribe:
  outputs/validation/analysis_v3.csv  (privado, git-ignored: lo leen los modelos R)
  outputs/v3/descriptives_v3.json     (agregados; lo integra 14_v3_models.R)
  outputs/v3/tables/*.csv
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PRIV = ROOT / "data" / "private_v3"
VALIDATION = ROOT / "outputs" / "validation"
OUT = ROOT / "outputs" / "v3"
TABLES = OUT / "tables"

CUTOFF = pd.Timestamp("2026-10-17", tz="UTC")  # corte 2026-10-16 inclusive
EXCLUDED_KEY = {  # ANALYSIS_PLAN_v3.md §2.3
    "6ddc4a8fe7344ce2a5ca8db88b6b3059", "2e64446487175f3693326d8f374f7e3b",
    "9a5b071450869af1f0062e4614e96799", "de74a3c0ac677254023f518cf74187b2",
    "d3000ecafb2f9cecf2b43909743ae211",
}
FORMATS = {"SingleChoice": "SC", "TrueFalse": "TF", "MultipleChoice": "MC"}
BAND_LABELS = ["0-<10", "10-<20", "20-<30", "30-<45", "45-<60", "60+"]
BAND_EDGES = [0, 10, 20, 30, 45, 60, np.inf]


def tbool(s: pd.Series) -> pd.Series:
    return s.astype(str).str.lower().isin(["t", "true", "1"])


def build() -> tuple[pd.DataFrame, dict]:
    raw = pd.read_csv(PRIV / "q4_responses.csv")
    for c in ["OpenedAt", "ClosedAt", "SubmittedAt"]:
        raw[c] = pd.to_datetime(raw[c], utc=True, format="ISO8601")
    flow = {"extracted": len(raw)}
    df = raw[tbool(raw["evaluable"])].copy()
    flow["evaluable"] = len(df)
    df = df[df["SubmittedAt"] < CUTOFF]
    flow["within_cutoff"] = len(df)
    valid = (df["OpenedAt"].notna() & df["ClosedAt"].notna()
             & (df["SubmittedAt"] >= df["OpenedAt"]) & (df["SubmittedAt"] <= df["ClosedAt"]))
    df = df[valid].copy()
    flow["timestamp_valid"] = len(df)
    df["key_excluded"] = df["question_id"].isin(EXCLUDED_KEY)
    flow["after_key_exclusion"] = int((~df["key_excluded"]).sum())

    out = pd.DataFrame({
        "response_id": df["response_id"], "student_id": df["student_id"],
        "question_id": df["question_id"], "run_id": df["run_id"], "session_id": df["session_id"],
        "course": df["course_name"].str.strip().str.upper(), "term": df["term"],
        "question_type": df["QuestionType"],
        "concept": df["course_code"].astype(str) + "::" + df["ConceptTag"].astype(str).str.strip().str.lower(),
        "correct": tbool(df["IsCorrect"]).astype(int),
        "response_time_seconds": df["rt_seconds"].astype(float),
        "key_excluded": df["key_excluded"],
    })
    out.loc[df["ConceptTag"].isna().values, "concept"] = np.nan
    return out, flow


def b3(df: pd.DataFrame, other: str) -> dict:
    rows = []
    for concept, g in df.groupby("concept"):
        ok = True
        for f in ("SingleChoice", other):
            x = g[g["question_type"] == f]["correct"]
            if len(x) < 5 or x.all() or not x.any():
                ok = False
        if not ok:
            continue
        for f in ("SingleChoice", other):
            x = g[g["question_type"] == f]
            mc = x.loc[x["correct"] == 1, "response_time_seconds"].median()
            mi = x.loc[x["correct"] == 0, "response_time_seconds"].median()
            rows.append({"concept": concept, "format": FORMATS[f], "n": len(x), "accuracy": x["correct"].mean(),
                         "median_rt_correct": mc, "median_rt_incorrect": mi,
                         "correct_faster": bool(mc < mi)})
    t = pd.DataFrame(rows)
    t.to_csv(TABLES / f"b3_within_concept_SC_vs_{FORMATS[other]}.csv", index=False)
    if t.empty:
        return {"concepts": 0}
    sc = t[t["format"] == "SC"]
    ot = t[t["format"] == FORMATS[other]]
    return {
        "concepts": int(sc.shape[0]),
        "responses": int(t["n"].sum()),
        "SC_correct_faster": int(sc["correct_faster"].sum()),
        f"{FORMATS[other]}_correct_faster": int(ot["correct_faster"].sum()),
        f"{FORMATS[other]}_correct_slower": int((~ot["correct_faster"]).sum()),
        "both_directions_as_v2": int((sc.set_index("concept")["correct_faster"]
                                      & ~ot.set_index("concept")["correct_faster"]).sum()),
    }


def run_check(df: pd.DataFrame) -> list[dict]:
    g = df.groupby(["run_id", "course", "question_type"])
    per = g.apply(lambda x: pd.Series({
        "mc": x.loc[x["correct"] == 1, "response_time_seconds"].median(),
        "mi": x.loc[x["correct"] == 0, "response_time_seconds"].median(),
    }), include_groups=False).dropna().reset_index()
    per["correct_faster"] = per["mc"] < per["mi"]
    out = per.groupby(["course", "question_type"]).agg(
        comparable_question_runs=("run_id", "size"), correct_faster_runs=("correct_faster", "sum")).reset_index()
    out["incorrect_faster_runs"] = out["comparable_question_runs"] - out["correct_faster_runs"]
    out["percentage_correct_faster"] = out["correct_faster_runs"] / out["comparable_question_runs"] * 100
    out.to_csv(TABLES / "run_level_direction_v3.csv", index=False)
    return out.to_dict("records")


def main() -> None:
    for p in (VALIDATION, TABLES):
        p.mkdir(parents=True, exist_ok=True)
    full, flow = build()
    # Orden canónico (estudiante, run): los IDs sintéticos públicos lo preservan, así el
    # ajuste sobre el dataset público es idéntico al privado (Δ = 0), no solo ~1e-6.
    full = full.sort_values(["student_id", "run_id"]).reset_index(drop=True)
    full.to_csv(VALIDATION / "analysis_v3.csv", index=False)
    df = full[~full["key_excluded"]].copy()

    df["rt_band"] = pd.cut(df["response_time_seconds"], BAND_EDGES, labels=BAND_LABELS, right=False)
    bands = df.groupby(["question_type", "rt_band"], observed=False)["correct"].agg(["size", "sum"]).reset_index()
    bands.columns = ["question_type", "rt_band", "n", "correct"]
    bands["accuracy"] = bands["correct"] / bands["n"]
    bands.to_csv(TABLES / "rt_bands_v3.csv", index=False)

    support = df.groupby("question_type")["response_time_seconds"].describe(
        percentiles=[0.05, 0.5, 0.95, 0.99]).reset_index()
    support.to_csv(TABLES / "rt_support_v3.csv", index=False)

    def n_block(d):
        return {"responses": len(d), "students": d["student_id"].nunique(), "questions": d["question_id"].nunique(),
                "concepts": d["concept"].nunique(), "sessions": d["session_id"].nunique(),
                "by_format": d["question_type"].map(FORMATS).value_counts().to_dict(),
                "by_offering": {f"{c} {t}": int(n) for (c, t), n in d.groupby(["course", "term"]).size().items()},
                "accuracy": round(d["correct"].mean(), 4)}

    desc = {
        "flow": flow,
        "n_primary": n_block(df),
        "n_uncorrected": n_block(full),
        "excluded_key_responses": int(full["key_excluded"].sum()),
        "rt_p99_pooled": float(df["response_time_seconds"].quantile(0.99)),
        "rt_support": support.round(3).to_dict("records"),
        "b3_SC_vs_TF": b3(df, "TrueFalse"),
        "b3_SC_vs_MC": b3(df, "MultipleChoice"),
        "run_level_direction": run_check(df),
    }
    (OUT / "descriptives_v3.json").write_text(json.dumps(desc, indent=2, default=lambda o: o.item()), encoding="utf-8")
    print(json.dumps({k: desc[k] for k in ["flow", "n_primary", "b3_SC_vs_TF", "b3_SC_vs_MC"]}, indent=1,
                     default=lambda o: o.item()))


if __name__ == "__main__":
    main()
