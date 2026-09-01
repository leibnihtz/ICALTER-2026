options(warn = 1)
set.seed(20260901)
if (nzchar(Sys.getenv("R_LIBS_USER"))) {
  .libPaths(c(Sys.getenv("R_LIBS_USER"), .libPaths()))
}

required <- c("lme4", "broom.mixed", "dplyr", "readr")
missing <- required[!vapply(required, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing) > 0) {
  stop("Missing required R packages: ", paste(missing, collapse = ", "), call. = FALSE)
}

library(lme4)
library(broom.mixed)
library(dplyr)
library(readr)

df_all <- read_csv("outputs/validation/analysis_dataset.csv", show_col_types = FALSE) %>%
  mutate(
    correct = as.integer(correct),
    timestamp_valid = as.logical(timestamp_valid),
    course = factor(course),
    question_type = relevel(factor(question_type), ref = "SingleChoice"),
    student_id_hash = factor(student_id_hash),
    question_id = factor(question_id)
  ) %>%
  filter(!is.na(correct), !is.na(response_time_seconds), !is.na(z_log_response_time))
df_all <- df_all %>%
  mutate(
    log_response_time = log1p(response_time_seconds),
    z_log_response_time = as.numeric(scale(log_response_time))
  )

fit_glmm <- function(data, formula) {
  glmer(
    formula,
    data = data,
    family = binomial(link = "logit"),
    control = glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 2e5))
  )
}

coef_table <- function(model, check_name) {
  tidy(model, effects = "fixed", conf.int = TRUE, conf.method = "Wald") %>%
    transmute(
      check = check_name,
      term,
      estimate_log_odds = estimate,
      standard_error = std.error,
      z_value = statistic,
      p_value = p.value,
      odds_ratio = exp(estimate),
      CI95_lower = exp(conf.low),
      CI95_upper = exp(conf.high),
      n_observations = nobs(model),
      singular = isSingular(model, tol = 1e-4)
    )
}

m2_formula <- correct ~ z_log_response_time * question_type + course +
  (1 | student_id_hash) + (1 | question_id)

r1 <- fit_glmm(filter(df_all, timestamp_valid), m2_formula)
r2_threshold <- quantile(df_all$response_time_seconds, 0.99, na.rm = TRUE)
r2 <- fit_glmm(filter(df_all, timestamp_valid, response_time_seconds <= r2_threshold), m2_formula)
r3 <- fit_glmm(
  filter(df_all, timestamp_valid),
  correct ~ response_time_seconds * question_type + course +
    (1 | student_id_hash) + (1 | question_id)
)

robustness_all <- bind_rows(
  coef_table(r1, "R1_exclude_timestamp_invalid"),
  coef_table(r2, "R2_trim_above_p99"),
  coef_table(r3, "R3_raw_response_time")
)
write_csv(robustness_all, "outputs/models/robustness_checks.csv")

course_formula <- correct ~ z_log_response_time * question_type +
  (1 | student_id_hash) + (1 | question_id)

for (course_name in levels(df_all$course)) {
  subset <- filter(df_all, timestamp_valid, course == course_name)
  path <- paste0(
    "outputs/models/robustness_",
    gsub("[^a-z0-9]+", "_", tolower(course_name)),
    ".csv"
  )
  result <- tryCatch(
    coef_table(fit_glmm(subset, course_formula), paste0("R4_", course_name)),
    error = function(e) tibble(check = paste0("R4_", course_name), error = conditionMessage(e))
  )
  write_csv(result, path)
}

print("Robustness outputs written.")
