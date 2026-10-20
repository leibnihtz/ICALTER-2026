"""ICALTER v3 — Parte A (A0, A1, A3, A4, A7) sobre la extracción privada.

Lee data/private_v3/q*.csv (sql_extract_icalter_v3.sql, pasos 1 y 2) y escribe
audit/icalter_v3_facts.json + audit/a1_candidates.csv. Solo agrega: no copia
timestamps exactos ni texto libre a los outputs.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PRIV = ROOT / "data" / "private_v3"
AUDIT = ROOT / "audit"

EVAL_TYPES = ["SingleChoice", "TrueFalse", "MultipleChoice"]
# Fechas de despliegue (memoria del proyecto + tags git de LeibtiMeter):
# v2.1-privacy-and-fr9 (a38c100) desplegado 2026-09-27; v2.2 desplegado 2026-09-29.
# [PENDIENTE] confirmar con `git reflog --date=iso` en el droplet.
DEPLOYS = [("v2.0", None), ("v2.1", "2026-09-27"), ("v2.2", "2026-09-29")]


def tbool(s: pd.Series) -> pd.Series:
    return s.astype(str).str.lower().isin(["t", "true", "1"])


def version_at(ts: pd.Series) -> pd.Series:
    out = pd.Series("v2.0", index=ts.index)
    for name, day in DEPLOYS[1:]:
        out[ts >= pd.Timestamp(day, tz="UTC")] = name
    return out


def num(x):
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return None if np.isnan(x) else round(float(x), 4)
    return x


def load():
    q2 = pd.read_csv(PRIV / "q2_sessions.csv")
    q3 = pd.read_csv(PRIV / "q3_questions.csv")
    q4 = pd.read_csv(PRIV / "q4_responses.csv")
    for c in ["evaluable", "known_key_error", "after_close", "HasCorrectAnswer", "manual_close"]:
        q4[c] = tbool(q4[c])
    q4["IsCorrect"] = q4["IsCorrect"].map({"t": True, "f": False})
    for c in ["OpenedAt", "ClosedAt", "SubmittedAt"]:
        q4[c] = pd.to_datetime(q4[c], utc=True, format="ISO8601")
    for c in ["StartedAt", "EndedAt"]:
        q2[c] = pd.to_datetime(q2[c], utc=True, format="ISO8601")
    for c in ["CreatedAt", "UpdatedAt", "first_opened_at", "last_opened_at"]:
        q3[c] = pd.to_datetime(q3[c], utc=True, format="ISO8601")
    q3["known_key_error"] = tbool(q3["known_key_error"])
    q3["IsActive"] = tbool(q3["IsActive"])
    q4["course"] = q4["course_name"].str.strip().str.upper()
    q4["offering"] = q4["course"] + " " + q4["term"]
    q4["concept"] = np.where(
        q4["ConceptTag"].notna(),
        q4["course_code"].astype(str) + "::" + q4["ConceptTag"].astype(str).str.strip().str.lower(),
        None,
    )
    return q2, q3, q4


def a0(q2, q4):
    courses = q4[["course_id_raw", "offering"]].drop_duplicates()
    q2 = q2.merge(courses, on="course_id_raw", how="left")
    rows = []
    for off, g in q4.groupby("offering"):
        s = q2[q2["offering"] == off]
        ev = g[g["evaluable"]]
        rows.append({
            "offering": off,
            "sessions_total": len(s),
            "sessions_with_responses": int((s["n_responses"] > 0).sum()),
            "runs": g["run_id"].nunique(),
            "questions": g["question_id"].nunique(),
            "students": g["student_id"].nunique(),
            "responses_total": len(g),
            "responses_evaluable": len(ev),
            **{f"evaluable_{t}": int((ev["QuestionType"] == t).sum()) for t in EVAL_TYPES},
            "first_session_date": str(s["StartedAt"].min().date()),
            "last_session_date": str(s["StartedAt"].max().date()),
        })
    terms = q4.groupby("term")["student_id"].apply(set)
    both = set.intersection(*terms.values) if len(terms) > 1 else set()
    q2["version"] = version_at(q2["StartedAt"])
    q4["version"] = version_at(q4["SubmittedAt"])
    closed = q2[q2["Status"] == "Closed"]
    cutoff = closed["EndedAt"].max()
    return {
        "by_offering": rows,
        "totals": {
            "sessions": len(q2), "responses": len(q4),
            "responses_evaluable": int(q4["evaluable"].sum()),
            "students": q4["student_id"].nunique(),
            "students_in_both_terms": len(both),
        },
        "version_by_session": q2.groupby("version").agg(
            sessions=("session_id", "size"), responses=("n_responses", "sum")).reset_index().to_dict("records"),
        "evaluable_responses_by_version": q4[q4["evaluable"]].groupby("version").size().to_dict(),
        "sessions_spanning_a_deploy": int((version_at(q2["StartedAt"]) != version_at(q2["EndedAt"])).sum()),
        "cutoff_proposed": {
            "last_closed_session_end_date": str(cutoff.date()),
            "all_sessions_closed": bool((q2["Status"] == "Closed").all()),
        },
        "deploy_dates_assumed": {k: v for k, v in DEPLOYS},
    }


def a1(q4):
    ev = q4[q4["evaluable"]]
    per_q = ev.groupby("question_id").agg(
        term=("term", "first"), offering=("offering", "first"), format=("QuestionType", "first"),
        concept_tagged=("ConceptTag", lambda s: bool(s.notna().any())),
        known_key_error=("known_key_error", "first"),
        n=("IsCorrect", "size"), accuracy=("IsCorrect", "mean"),
    ).reset_index()
    per_q["in_v2_dataset"] = per_q["term"] == "2026-1"
    cand = per_q[per_q["known_key_error"] | (
        (per_q["n"] >= 10) & ((per_q["accuracy"] < 0.10) | (per_q["accuracy"] > 0.99)))].copy()
    cand["reason"] = np.where(cand["known_key_error"], "known_key_error (ICITS)",
                              np.where(cand["accuracy"] < 0.10, "accuracy<10%", "accuracy>99%"))
    cand = cand.sort_values(["known_key_error", "accuracy"], ascending=[False, True])
    cand.to_csv(AUDIT / "a1_candidates.csv", index=False)
    new_cand = cand[~cand["known_key_error"]]
    return {
        "known_key_errors": {
            "questions": int(cand["known_key_error"].sum()),
            "responses": int(ev["known_key_error"].sum()),
            "detail": cand[cand["known_key_error"]][["question_id", "offering", "format", "n", "accuracy", "in_v2_dataset"]]
                .to_dict("records"),
        },
        "threshold_candidates": new_cand[["question_id", "offering", "format", "n", "accuracy", "reason", "concept_tagged"]]
            .to_dict("records"),
        "n_low_accuracy": int((new_cand["reason"] == "accuracy<10%").sum()),
        "n_high_accuracy": int((new_cand["reason"] == "accuracy>99%").sum()),
        # Solo las de accuracy baja: una clave errónea baja el acierto; 100% no la sugiere.
        "step3_cand_argument": ",".join(f"'{q}'" for q in new_cand.loc[new_cand["reason"] == "accuracy<10%", "question_id"]),
    }


def a3(q2):
    return {
        "sessions": len(q2),
        "with_score_policy": int(tbool(q2["has_score_policy"]).sum()),
        "speed_bonus_enabled": int(tbool(q2["SpeedBonusEnabled"]).sum()),
        "max_speed_bonus_nonzero": int((q2["MaxSpeedBonus"].fillna(0) > 0).sum()),
        "speed_bonus_score_events": int(q2["n_speed_bonus_events"].sum()),
        "policies": q2.groupby(["policy_name", "ParticipationPoints", "CorrectPoints", "IncorrectPoints",
                                "AllowNegativeScore"], dropna=False).size().reset_index(name="sessions")
            .astype(object).to_dict("records"),
    }


def a4(q4):
    ev = q4[q4["evaluable"]]
    rt = ev.groupby("term")["rt_seconds"].agg(
        n="size", median="median", p95=lambda s: s.quantile(0.95), p99=lambda s: s.quantile(0.99), max="max")
    return {
        "runs_with_time_limit": int(q4.drop_duplicates("run_id")["TimeLimitSeconds"].notna().sum()),
        "runs_total": q4["run_id"].nunique(),
        "time_limit_distribution": q4.drop_duplicates("run_id")["TimeLimitSeconds"].value_counts(dropna=False)
            .rename(lambda k: "null" if pd.isna(k) else int(k)).to_dict(),
        "responses_over_time_limit": int(pd.Series(q4["over_time_limit"]).astype(str).str.lower().eq("t").sum()),
        "responses_after_close": int(q4["after_close"].sum()),
        "evaluable_after_close": int(ev["after_close"].sum()),
        "runs_closed_manually": int(q4.drop_duplicates("run_id")["manual_close"].sum()),
        "rt_seconds_by_term_evaluable": {t: {k: num(v) for k, v in r.items()} for t, r in rt.iterrows()},
    }


def a7(q3, q4):
    ev = q4[q4["evaluable"] & ~q4["known_key_error"]]
    qs = ev.drop_duplicates("question_id")
    tagged = qs["ConceptTag"].notna()
    lo = qs["LearningOutcome"].notna()
    evt = ev[ev["concept"].notna()]
    per_c = evt.groupby("concept").agg(
        questions=("question_id", "nunique"), responses=("response_id", "size"),
        formats=("QuestionType", lambda s: "+".join(sorted({"SingleChoice": "SC", "TrueFalse": "TF",
                                                             "MultipleChoice": "MC"}[x] for x in set(s)))),
        terms=("term", lambda s: "+".join(sorted(set(s)))),
    )
    combos = per_c.groupby("formats").agg(concepts=("responses", "size"), responses=("responses", "sum"))
    def has(*fs):
        m = per_c["formats"].apply(lambda f: all(x in f.split("+") for x in fs))
        return {"concepts": int(m.sum()), "responses": int(per_c.loc[m, "responses"].sum())}
    # B3: SC y TF con ≥5 respuestas por formato y al menos 1 correcta y 1 incorrecta por formato
    def b3_ok(g, fa, fb):
        for f in (fa, fb):
            x = g[g["QuestionType"] == f]["IsCorrect"]
            if len(x) < 5 or x.all() or not x.any():
                return False
        return True
    b3_sc_tf = sum(b3_ok(g, "SingleChoice", "TrueFalse") for _, g in evt.groupby("concept"))
    b3_sc_mc = sum(b3_ok(g, "SingleChoice", "MultipleChoice") for _, g in evt.groupby("concept"))

    # Cuándo se etiquetó: UpdatedAt ≤ primera apertura ⇒ la etiqueta ya existía al usarse
    q3m = q3.merge(ev[["question_id", "term"]].drop_duplicates("question_id"), on="question_id")
    q3m = q3m[q3m["ConceptTag"].notna()]
    q3m["tag_before_first_use"] = q3m["UpdatedAt"] <= q3m["first_opened_at"]
    when = q3m.groupby("term")["tag_before_first_use"].agg(["sum", "size"]).rename(
        columns={"sum": "updated_before_first_use", "size": "tagged_questions"})

    concept_terms = per_c["terms"].value_counts().to_dict()
    return {
        "scope": "evaluable responses, excluding the 3 known key-error questions",
        "coverage": {
            "questions": len(qs), "questions_with_concept": int(tagged.sum()),
            "questions_with_learning_outcome": int(lo.sum()),
            "responses": len(ev), "responses_with_concept": len(evt),
            "distinct_concepts_course_scoped": int(per_c.shape[0]),
        },
        "per_concept": {
            k: {"min": num(per_c[k].min()), "median": num(per_c[k].median()), "max": num(per_c[k].max())}
            for k in ["questions", "responses"]
        },
        "format_combinations": {k: {"concepts": int(v["concepts"]), "responses": int(v["responses"])}
                                for k, v in combos.iterrows()},
        "concepts_with": {"SC+TF": has("SC", "TF"), "SC+MC": has("SC", "MC"),
                          "TF+MC": has("TF", "MC"), "SC+TF+MC": has("SC", "TF", "MC")},
        "b3_eligible_concepts": {"SC_vs_TF": int(b3_sc_tf), "SC_vs_MC": int(b3_sc_mc)},
        "concepts_by_terms_present": concept_terms,
        "tagging_time": {t: {k: int(v) for k, v in r.items()} for t, r in when.iterrows()},
    }


def main() -> None:
    AUDIT.mkdir(exist_ok=True)
    q2, q3, q4 = load()
    facts = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "data/private_v3 (sql_extract_icalter_v3.sql steps 1-2, extracted 2026-10-20)",
        "A0": a0(q2, q4), "A1": a1(q4), "A3": a3(q2), "A4": a4(q4), "A7": a7(q3, q4),
    }
    out = AUDIT / "icalter_v3_facts.json"
    out.write_text(json.dumps(facts, indent=2, ensure_ascii=False, default=num), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
