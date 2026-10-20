# ICALTER v3 — A8: re-ajusta M1/M2 sobre el CSV congelado de la v2 y compara
# contra outputs/results_summary_v2.json (que no se modifica).
# Mismos filtros que common.py::load_analysis_data y mismas fórmulas que 04/08.
options(warn = 1)
set.seed(20260901)
if (nzchar(Sys.getenv("R_LIBS_USER"))) .libPaths(c(Sys.getenv("R_LIBS_USER"), .libPaths()))
suppressPackageStartupMessages({ library(lme4); library(dplyr); library(readr); library(jsonlite) })

df <- read_csv("data/leibtimeter_paper_base.csv", show_col_types = FALSE) %>%
  mutate(
    across(c(opened_at, closed_at, submitted_at), ~ as.POSIXct(.x, tz = "UTC")),
    correct = as.integer(tolower(as.character(is_correct)) %in% c("t", "true", "1")),
    correct = ifelse(is.na(is_correct), NA, correct),
    response_time_seconds = as.numeric(response_time_seconds),
    timestamp_valid = !is.na(submitted_at) & !is.na(opened_at) & !is.na(closed_at) &
      submitted_at >= opened_at & submitted_at <= closed_at
  ) %>%
  filter(!is.na(correct), !is.na(response_time_seconds), timestamp_valid) %>%
  mutate(
    course = factor(course),
    question_type = relevel(factor(question_type), ref = "SingleChoice"),
    student_id_hash = factor(student_id_hash), question_id = factor(question_id),
    z_log_response_time = as.numeric(scale(log1p(response_time_seconds)))
  )

ctrl <- glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 2e5))
m1 <- glmer(correct ~ z_log_response_time + question_type + course +
              (1 | student_id_hash) + (1 | question_id), df, binomial, control = ctrl)
m2 <- glmer(correct ~ z_log_response_time * question_type + course +
              (1 | student_id_hash) + (1 | question_id), df, binomial, control = ctrl)
lrt <- anova(m1, m2)

v2 <- fromJSON("outputs/results_summary_v2.json")
b <- fixef(m2); se <- sqrt(diag(vcov(m2)))
or_ci <- function(t) c(or = exp(b[[t]]), lo = exp(b[[t]] - 1.959964 * se[[t]]), hi = exp(b[[t]] + 1.959964 * se[[t]]))
tf <- or_ci("z_log_response_time:question_typeTrueFalse")
mc <- or_ci("z_log_response_time:question_typeMultipleChoice")

ref <- list(
  n = v2$dataset$responses_analysis, aic_m2 = v2$primary_model$aic,
  chisq = v2$interaction_global_test$chisq,
  or_tf = v2$question_type_interactions$TrueFalse_vs_SingleChoice$odds_ratio,
  or_mc = v2$question_type_interactions$MultipleChoice_vs_SingleChoice$odds_ratio
)
got <- list(n = nobs(m2), aic_m2 = AIC(m2), chisq = lrt$Chisq[2], or_tf = tf[["or"]], or_mc = mc[["or"]])
diff <- mapply(function(a, b) abs(a - b), got, ref)
out <- list(
  refit = c(got, list(or_tf_ci = unname(tf[c("lo", "hi")]), or_mc_ci = unname(mc[c("lo", "hi")]),
                      lrt_df = lrt$Df[2], lrt_p = lrt$`Pr(>Chisq)`[2],
                      students = nlevels(droplevels(df$student_id_hash)),
                      questions = nlevels(droplevels(df$question_id)),
                      converged = is.null(m2@optinfo$conv$lme4$messages), singular = isSingular(m2))),
  reference_v2 = ref, abs_diff = as.list(diff),
  reproduced = diff[["n"]] == 0 && all(unlist(diff[c("aic_m2", "chisq", "or_tf", "or_mc")]) < 1e-3)
)
dir.create("audit", showWarnings = FALSE)
write_json(out, "audit/a8_reproduce_v2.json", auto_unbox = TRUE, digits = 10, pretty = TRUE)
cat("reproduced:", out$reproduced, "\n")
