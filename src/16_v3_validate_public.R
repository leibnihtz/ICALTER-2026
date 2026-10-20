# ICALTER v3 — validación privado vs. público: M2 y M4 deben dar Δ = 0.
options(warn = 1)
if (nzchar(Sys.getenv("R_LIBS_USER"))) .libPaths(c(Sys.getenv("R_LIBS_USER"), .libPaths()))
suppressPackageStartupMessages({ library(lme4); library(dplyr); library(readr); library(jsonlite) })

prep <- function(d) d %>% filter(!key_excluded) %>% mutate(
  question_type = relevel(factor(question_type), ref = "SingleChoice"),
  course = factor(course), term = factor(term),
  z = as.numeric(scale(log1p(response_time_seconds))))

priv <- read_csv("outputs/validation/analysis_v3.csv", show_col_types = FALSE) %>%
  transmute(student_id, question_id, concept, course, term, question_type,
            response_time_seconds, correct, key_excluded = as.logical(key_excluded)) %>% prep()
pub <- read_csv("data/public_v3/leibtimeter_public_v3.csv", show_col_types = FALSE) %>%
  transmute(student_id, question_id, concept = concept_id, course, term, question_type,
            response_time_seconds, correct = is_correct, key_excluded = key_excluded == 1) %>% prep()

ctrl <- glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 2e5))
fx <- "correct ~ z * question_type + course + term + (1 | student_id) + (1 | question_id)"
cmp <- function(formula) {
  a <- glmer(as.formula(formula), priv, binomial, control = ctrl)
  b <- glmer(as.formula(formula), pub, binomial, control = ctrl)
  list(max_abs_coef_diff = max(abs(fixef(a) - fixef(b))), aic_diff = abs(AIC(a) - AIC(b)),
       loglik_diff = abs(as.numeric(logLik(a)) - as.numeric(logLik(b))), aic = AIC(a))
}
out <- list(
  rows = c(private = nrow(priv), public = nrow(pub)),
  students = c(private = n_distinct(priv$student_id), public = n_distinct(pub$student_id)),
  questions = c(private = n_distinct(priv$question_id), public = n_distinct(pub$question_id)),
  concepts = c(private = n_distinct(priv$concept), public = n_distinct(pub$concept)),
  M2 = cmp(fx), M4 = cmp(paste(fx, "+ (1 | concept)"))
)
out$delta_zero <- out$M2$max_abs_coef_diff < 1e-8 && out$M4$max_abs_coef_diff < 1e-8 &&
  out$M2$aic_diff < 1e-6 && out$M4$aic_diff < 1e-6 && out$rows[["private"]] == out$rows[["public"]]
write_json(out, "outputs/v3/public_validation.json", auto_unbox = TRUE, digits = 12, pretty = TRUE)
cat("delta_zero:", out$delta_zero, "\n")
