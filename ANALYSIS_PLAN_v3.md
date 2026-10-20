# ANALYSIS PLAN — ICALTER 2026 v3

Fixed and committed before any v3 model was fitted (not formally preregistered).
Decisions confirmed by the author on 2026-10-20 after the Part A audit
(`audit/icalter_v3_facts.json`, `audit/a1_candidates.csv`, `audit/a8_reproduce_v2.json`).

## 1. Data

- Source: production LeibtiMeter DB, read-only extraction on 2026-10-20 with
  `sql_extract_icalter_v3.sql` (steps 1–3). Private files in `data/private_v3/` (git-ignored);
  IDs pseudonymized as md5(id || salt), salt kept outside the repository.
- Offerings (4): BIG DATA 2026-1, REDES II 2026-1, BIG DATA 2026-2, REDES II 2026-2.
  Excluded: every other course (colleagues' pilot / other programs).
- Cut-off date: **2026-10-16** (end of the last closed session). All 26 sessions are closed.
- Versions: 21 sessions under v2.0 (2,088 evaluable responses = ICITS evaluable set),
  5 sessions under v2.2; none under v2.1. RT definition unchanged across versions (A2).

## 2. Inclusion rules (applied in this order)

1. Evaluable: format ∈ {SingleChoice, TrueFalse, MultipleChoice}, `HasCorrectAnswer`, `IsCorrect` not null
   (same as LearningAnalytics.cs and the ICITS freeze).
2. Timestamp-valid (same as v2, `common.py`): OpenedAt ≤ SubmittedAt ≤ ClosedAt, all present.
3. Answer-key correction (A1) — **exclude 5 questions**, all their responses:

   | question_id (salted md5) | Offering | Format | n | Reason |
   |---|---|---|---|---|
   | 6ddc4a8fe7344ce2a5ca8db88b6b3059 | REDES II 2026-2 | SC | 31 | no option keyed |
   | 2e64446487175f3693326d8f374f7e3b | REDES II 2026-1 | SC | 16 | no option keyed (ICITS known) |
   | 9a5b071450869af1f0062e4614e96799 | BIG DATA 2026-1 | MC | 29 | a true option not keyed (ICITS known) |
   | de74a3c0ac677254023f518cf74187b2 | REDES II 2026-1 | SC | 14 | duplicated options, no correct option (ICITS known) |
   | d3000ecafb2f9cecf2b43909743ae211 | BIG DATA 2026-1 | MC | 28 | all options keyed; key ambiguous |

   Kept: ea585f54a9cd0dcb70eb6f4f5cbb5b78 (MC, 0% accuracy, key defensible) and the
   14 questions with 100% accuracy (easy items; a wrong key does not raise accuracy).
   No re-scoring is done: `IsCorrect` is used as stored by the backend.

## 3. Variables

- Outcome: `correct` (0/1).
- RT: SubmittedAt − OpenedAt (server clock), transformed `z = scale(log(1 + RT))` on the analysis set.
- Format: factor, reference SingleChoice.
- Course: BIG DATA / REDES II (by course code). Term: 2026-1 (reference) / 2026-2.
- Concept: course code + lower-cased trimmed ConceptTag (a tag is one concept per course
  across both terms). Question IDs are unique, so `(1|question)` is nested in concept.
- Random effects in every model: `(1|student) + (1|question)`.

## 4. Models (lme4::glmer, binomial logit, ML)

Optimizer `bobyqa` (maxfun 2e5). If a model fails to converge, one retry with `Nelder_Mead`;
no further attempts. Convergence and singularity (`isSingular`, tol 1e-4) are reported for all.

| Model | Fixed part | Role |
|---|---|---|
| M1 | z + format + course + term | baseline |
| **M2** | z × format + course + term | **primary (RQ1)** |
| M3-course | z × format × course + term | consistency across courses (LRT vs M2) |
| M3-term | z × format × term + course | consistency across terms (LRT vs M2) |
| M2 by term | z × format + course, fitted on each term | descriptive table only |
| M4 | M2 + (1\|concept) | RQ2a |
| M5 | M2 + (1 + z\|concept) | RQ2a/b |

Reported: LRT M2 vs M1 (primary test), AIC, ORs with Wald 95% CI for the SC slope, TF×RT and MC×RT;
LRT M5 vs M4; SD of the concept random slope vs |log OR(TF×RT)|.

## 5. RQ2 scenario rule (fixed now)

Using the TF×RT interaction (the v2 effect):
1. **Format holds within concept** — 95% CI of TF×RT excludes 1 in M4 and in M5 (or in M4 if M5 is
   singular/non-convergent), same direction as M2, and no detectable concept slope variance
   (M5 singular, or LRT M5 vs M4 p ≥ .05).
2. **Format holds and concepts vary** — as (1), but M5 is non-singular and LRT M5 vs M4 p < .05.
3. **Format disappears** — 95% CI of TF×RT includes 1 in M4 or in M5.

If M5 is singular it is reported as "no detectable heterogeneity across concepts at this sample size".

## 6. B3 — within-concept descriptive check

Concepts with SC and TF, ≥ 5 responses per format and ≥ 1 correct and ≥ 1 incorrect per format.
Per concept × format: accuracy, median RT of correct and of incorrect responses, sign of
(median correct − median incorrect). Summary: in how many concepts correct responses are faster
in SC, and slower in TF. Same for SC vs MC. Descriptive only.

## 7. B4 — robustness (in this priority order)

1. M2 with uncorrected labels (the 5 excluded questions put back, stored `IsCorrect`).
2. M2 restricted to 2026-1, with the correction applied (compare with v2).
3. M2 without responses above the pooled p99 of RT.
4. M2 with `(1 + z|question)`.
5. Run-level check as in v2 §IV.D: per question run with both outcomes, whether the median RT of
   correct responses is below that of incorrect ones, by course × format.

## 8. Figures and outputs

- Fig. 1: accuracy by RT band (0–10–20–30–45–60+ s) and format, pooled.
- Fig. 2: M2 predicted probability by format over each format's empirical P5–P95 RT range.
- Fig. 3 only if M5 converges and is non-singular.
- All numbers in `outputs/results_summary_v3.json`, written by script. `results_summary_v2.json` is not modified.
- Public dataset v3: synthetic student/question/concept IDs, no exact timestamps, no free text;
  private-vs-public validation must give Δ = 0.
