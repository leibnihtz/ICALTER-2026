# LeibtiMeter / ICALTER 2026 Final Validation Report V2

## Executive Decision

Decision: **B. Paper is viable, but the narrative/title must be narrowed.**

Recommended claim: The primary model supports moderation by question format, especially for TrueFalse versus SingleChoice, but robustness should be reported cautiously because the raw-time R3 model did not fully converge.

## Q1. Does M2 fit significantly better than the model without the interaction?

Yes. M1 vs M2 LRT: chi-square = 16.522, df = 2, p = 2.58e-04, delta AIC = -12.522.

## Q2. Which question formats show evidence of a different relationship?

- MultipleChoice vs SingleChoice: OR 1.556 [0.850, 2.847], p = 0.152; no strong evidence of difference.
- TrueFalse vs SingleChoice: OR 3.496 [1.891, 6.462], p = 6.54e-05; evidence of difference.

## Q3. Is the TrueFalse pattern supported by multiple question runs?

TrueFalse comparable question runs with both correct and incorrect responses: 16.
- BIG DATA: 2 correct-faster runs, 7 incorrect-faster runs, 22.222% correct-faster.
- REDES II: 1 correct-faster runs, 6 incorrect-faster runs, 14.286% correct-faster.

This is descriptive validation only, not an inferential test.

## Q4. Are model predictions shown only in supported regions?

Yes. Figure 3 v2 uses question-type-specific empirical support, capped at each type's P95 response time.
- MultipleChoice: n = 360, P95 = 77.401 s, max = 118.837 s.
- SingleChoice: n = 550, P95 = 46.225 s, max = 119.701 s.
- TrueFalse: n = 321, P95 = 37.458 s, max = 127.401 s.

## Q5. Does M3 provide evidence that the pattern differs by course?

M2 vs M3 LRT: chi-square = 3.924, df = 5, p = 0.560, delta AIC = 6.076.
There is no strong formal evidence of a course interaction; this is not proof that the courses are identical.

## Q6. Is R3 statistically valid after independent refitting?

Yes for coefficient extraction, but no as a clean inferential robustness model. The standard errors from `summary(model)$coefficients` match `sqrt(diag(vcov(model)))` within tolerance.
Maximum SE absolute difference: 0.0000000000.
R3 convergence status: not converged.

## Q7. Do robustness checks preserve the qualitative conclusion?

R3 should not be used as strong robustness evidence because it did not pass all validation requirements.
- SingleChoice response-time slope: M2 negative (not significant), R3 negative (significant), consistent = True.
- MultipleChoice vs SingleChoice slope difference: M2 positive (not significant), R3 positive (significant), consistent = True.
- TrueFalse vs SingleChoice slope difference: M2 positive (significant), R3 positive (significant), consistent = True.

## Q8. Most Defensible Scientific Claim

The primary model supports moderation by question format, especially for TrueFalse versus SingleChoice, but robustness should be reported cautiously because the raw-time R3 model did not fully converge.

The claim should remain observational and associative. The analysis does not show that response time causes correctness or that LeibtiMeter improves learning.

## Descriptive Time-Band Check

Response-time bands are descriptive support for the model and should not be interpreted inferentially.
- MultipleChoice 0-<10: n = 12, accuracy = 0.083.
- MultipleChoice 10-<20: n = 83, accuracy = 0.494.
- MultipleChoice 20-<30: n = 124, accuracy = 0.532.
- MultipleChoice 30-<45: n = 86, accuracy = 0.465.
- MultipleChoice 45-<60: n = 24, accuracy = 0.292.
- MultipleChoice 60+: n = 31, accuracy = 0.000.
- SingleChoice 0-<10: n = 62, accuracy = 0.823.
- SingleChoice 10-<20: n = 232, accuracy = 0.862.
- SingleChoice 20-<30: n = 151, accuracy = 0.834.
- SingleChoice 30-<45: n = 71, accuracy = 0.676.
- SingleChoice 45-<60: n = 24, accuracy = 0.583.
- SingleChoice 60+: n = 10, accuracy = 0.600.
- TrueFalse 0-<10: n = 73, accuracy = 0.740.
- TrueFalse 10-<20: n = 160, accuracy = 0.706.
- TrueFalse 20-<30: n = 51, accuracy = 0.745.
- TrueFalse 30-<45: n = 31, accuracy = 0.903.
- TrueFalse 45-<60: n = 4, accuracy = 0.750.
- TrueFalse 60+: n = 2, accuracy = 1.000.

## Title Recommendation

Title recommendation: **MODIFY**

The candidate title is close, but a narrower title would better reflect that the strongest evidence is concentrated in the TrueFalse contrast.

Alternative titles:
- Question Format Moderates the Link Between Response Time and Correctness in Classroom Interaction Data
- Response Time Is Not a Universal Accuracy Signal: Evidence Across Classroom Question Formats
- Timing and Correctness in Real-Time Classroom Responses Across Computing Courses
