options(warn = 1)
set.seed(20260901)
if (nzchar(Sys.getenv("R_LIBS_USER"))) {
  .libPaths(c(Sys.getenv("R_LIBS_USER"), .libPaths()))
}

required <- c("lme4", "broom.mixed", "dplyr", "readr", "tidyr", "ggplot2", "scales")
missing <- required[!vapply(required, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing) > 0) {
  stop("Missing required R packages: ", paste(missing, collapse = ", "), call. = FALSE)
}

library(lme4)
library(broom.mixed)
library(dplyr)
library(readr)
library(tidyr)
library(ggplot2)

dir.create("outputs/models", recursive = TRUE, showWarnings = FALSE)
dir.create("outputs/figures", recursive = TRUE, showWarnings = FALSE)

df <- read_csv("outputs/validation/analysis_dataset.csv", show_col_types = FALSE) %>%
  mutate(
    correct = as.integer(correct),
    timestamp_valid = as.logical(timestamp_valid),
    course = factor(course),
    question_type = relevel(factor(question_type), ref = "SingleChoice"),
    student_id_hash = factor(student_id_hash),
    question_id = factor(question_id)
  ) %>%
  filter(timestamp_valid, !is.na(correct), !is.na(response_time_seconds), !is.na(z_log_response_time))
df <- df %>%
  mutate(
    log_response_time = log1p(response_time_seconds),
    z_log_response_time = as.numeric(scale(log_response_time))
  )

support <- read_csv("outputs/tables/response_time_support.csv", show_col_types = FALSE)

fit_glmm <- function(formula, data) {
  glmer(
    formula,
    data = data,
    family = binomial(link = "logit"),
    control = glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 2e5))
  )
}

m1 <- fit_glmm(
  correct ~ z_log_response_time + question_type + course +
    (1 | student_id_hash) + (1 | question_id),
  df
)
m2 <- fit_glmm(
  correct ~ z_log_response_time * question_type + course +
    (1 | student_id_hash) + (1 | question_id),
  df
)
m3 <- fit_glmm(
  correct ~ z_log_response_time * question_type * course +
    (1 | student_id_hash) + (1 | question_id),
  df
)

lrt_row <- function(a, b) {
  cmp <- as.data.frame(anova(a, b, test = "Chisq"))
  df_col <- if ("Chi Df" %in% names(cmp)) "Chi Df" else "Df"
  tibble(
    chisq = as.numeric(cmp$Chisq[2]),
    df = as.numeric(cmp[[df_col]][2]),
    p_value = as.numeric(cmp$`Pr(>Chisq)`[2]),
    AIC_reduced = AIC(a),
    AIC_full = AIC(b),
    delta_AIC = AIC(b) - AIC(a)
  )
}

lrt_m1_m2 <- lrt_row(m1, m2) %>%
  rename(AIC_M1 = AIC_reduced, AIC_M2 = AIC_full)
write_csv(lrt_m1_m2, "outputs/models/M1_vs_M2_lrt.csv")

lrt_m2_m3 <- lrt_row(m2, m3) %>%
  rename(AIC_M2 = AIC_reduced, AIC_M3 = AIC_full)
write_csv(lrt_m2_m3, "outputs/models/M2_vs_M3_lrt.csv")

r3 <- fit_glmm(
  correct ~ response_time_seconds * question_type + course +
    (1 | student_id_hash) + (1 | question_id),
  df
)

summary_coef <- as.data.frame(summary(r3)$coefficients)
summary_coef$term <- rownames(summary_coef)
rownames(summary_coef) <- NULL
vcov_se <- sqrt(diag(vcov(r3)))
vcov_se <- vcov_se[summary_coef$term]
se_diff <- abs(summary_coef$`Std. Error` - vcov_se)
if (any(se_diff > 1e-8, na.rm = TRUE)) {
  stop("R3 standard-error sanity check failed: summary SE and sqrt(diag(vcov)) differ.", call. = FALSE)
}

r3_coef <- summary_coef %>%
  transmute(
    term,
    estimate_log_odds = Estimate,
    standard_error = `Std. Error`,
    z_value = `z value`,
    p_value = `Pr(>|z|)`,
    odds_ratio = exp(Estimate),
    CI95_lower = exp(Estimate - 1.96 * `Std. Error`),
    CI95_upper = exp(Estimate + 1.96 * `Std. Error`),
    vcov_standard_error = as.numeric(vcov_se),
    se_vcov_abs_difference = se_diff
  )
write_csv(r3_coef, "outputs/models/R3_raw_time_coefficients_v2.csv")

vc_diag <- diag(vcov(r3))
re_var <- as.data.frame(VarCorr(r3))
r3_messages <- r3@optinfo$conv$lme4$messages
diag_lines <- c(
  "R3 raw response-time GLMM diagnostics",
  "",
  "Formula: correct ~ response_time_seconds * question_type + course + (1 | student_id_hash) + (1 | question_id)",
  paste0("Converged: ", is.null(r3_messages)),
  paste0("Convergence messages: ", ifelse(is.null(r3_messages), "none", paste(r3_messages, collapse = "; "))),
  paste0("Singular fit: ", isSingular(r3, tol = 1e-4)),
  paste0("AIC: ", AIC(r3)),
  paste0("BIC: ", BIC(r3)),
  paste0("logLik: ", as.numeric(logLik(r3))),
  paste0("n observations: ", nobs(r3)),
  "",
  "Variance-covariance matrix diagonal:",
  paste(names(vc_diag), vc_diag, sep = ": "),
  "",
  "Random-effect variances:",
  paste(re_var$grp, re_var$var1, re_var$vcov, sep = " | "),
  "",
  paste0("SE sanity check passed: max absolute difference = ", max(se_diff, na.rm = TRUE))
)
writeLines(diag_lines, "outputs/models/R3_raw_time_diagnostics_v2.txt")

direction <- function(x) {
  ifelse(x > 0, "positive", ifelse(x < 0, "negative", "zero"))
}

m2_coef <- read_csv("outputs/models/M2_coefficients.csv", show_col_types = FALSE)
comparison <- tibble(
  term_concept = c(
    "SingleChoice response-time slope",
    "MultipleChoice vs SingleChoice slope difference",
    "TrueFalse vs SingleChoice slope difference"
  ),
  M2_term = c(
    "z_log_response_time",
    "z_log_response_time:question_typeMultipleChoice",
    "z_log_response_time:question_typeTrueFalse"
  ),
  R3_term = c(
    "response_time_seconds",
    "response_time_seconds:question_typeMultipleChoice",
    "response_time_seconds:question_typeTrueFalse"
  )
) %>%
  rowwise() %>%
  mutate(
    M2_estimate = m2_coef$estimate_log_odds[match(M2_term, m2_coef$term)],
    M2_p_value = m2_coef$p_value[match(M2_term, m2_coef$term)],
    R3_estimate = r3_coef$estimate_log_odds[match(R3_term, r3_coef$term)],
    R3_p_value = r3_coef$p_value[match(R3_term, r3_coef$term)],
    M2_direction = direction(M2_estimate),
    M2_significant = M2_p_value < 0.05,
    R3_direction = direction(R3_estimate),
    R3_significant = R3_p_value < 0.05,
    qualitative_consistency = M2_direction == R3_direction
  ) %>%
  ungroup() %>%
  select(term_concept, M2_direction, M2_significant, R3_direction, R3_significant, qualitative_consistency)
write_csv(comparison, "outputs/models/R3_vs_M2_comparison.csv")

fixed_link <- function(model_obj, newdata) {
  tt <- delete.response(terms(model_obj, fixed.only = TRUE))
  X <- model.matrix(tt, newdata)
  beta <- fixef(model_obj)
  X <- X[, names(beta), drop = FALSE]
  fit <- as.vector(X %*% beta)
  se <- sqrt(diag(X %*% as.matrix(vcov(model_obj)) %*% t(X)))
  list(fit = fit, se.fit = se)
}

log_mean <- mean(log1p(df$response_time_seconds), na.rm = TRUE)
log_sd <- sd(log1p(df$response_time_seconds), na.rm = TRUE)
candidate_times <- c(5, 10, 20, 30, 45, 60)

pred_grid <- expand_grid(
  course = levels(df$course),
  question_type = levels(df$question_type),
  response_time_seconds = candidate_times
) %>%
  left_join(support %>% select(question_type, minimum, p95), by = "question_type") %>%
  mutate(
    within_empirical_support = response_time_seconds >= minimum & response_time_seconds <= p95
  ) %>%
  filter(within_empirical_support) %>%
  mutate(
    question_type = factor(question_type, levels = levels(df$question_type)),
    course = factor(course, levels = levels(df$course)),
    z_log_response_time = (log1p(response_time_seconds) - log_mean) / log_sd,
    student_id_hash = df$student_id_hash[1],
    question_id = df$question_id[1]
  )

pred_link <- fixed_link(m2, pred_grid)
predictions <- pred_grid %>%
  mutate(
    fit_link = pred_link$fit,
    se_link = pred_link$se.fit,
    predicted_probability = plogis(fit_link),
    CI95_lower = plogis(fit_link - 1.96 * se_link),
    CI95_upper = plogis(fit_link + 1.96 * se_link)
  ) %>%
  select(course, question_type, response_time_seconds, predicted_probability,
         CI95_lower, CI95_upper, within_empirical_support)
write_csv(predictions, "outputs/models/M2_predicted_probabilities_v2.csv")

plot_grid <- support %>%
  select(question_type, minimum, p95) %>%
  rowwise() %>%
  mutate(response_time_seconds = list(seq(minimum, p95, length.out = 120))) %>%
  unnest(response_time_seconds) %>%
  ungroup() %>%
  tidyr::crossing(course = levels(df$course)) %>%
  mutate(
    question_type = factor(question_type, levels = levels(df$question_type)),
    course = factor(course, levels = levels(df$course)),
    z_log_response_time = (log1p(response_time_seconds) - log_mean) / log_sd,
    student_id_hash = df$student_id_hash[1],
    question_id = df$question_id[1]
  )

plot_link <- fixed_link(m2, plot_grid)
plot_df <- plot_grid %>%
  mutate(
    fit_link = plot_link$fit,
    se_link = plot_link$se.fit,
    predicted_probability = plogis(fit_link),
    CI95_lower = plogis(fit_link - 1.96 * se_link),
    CI95_upper = plogis(fit_link + 1.96 * se_link)
  )

rug_df <- df %>%
  group_by(course, question_type) %>%
  group_modify(~ slice_sample(.x, n = min(80, nrow(.x)), replace = FALSE)) %>%
  ungroup()

p <- ggplot(plot_df, aes(x = response_time_seconds, y = predicted_probability,
                         color = question_type, fill = question_type)) +
  geom_ribbon(aes(ymin = CI95_lower, ymax = CI95_upper), alpha = 0.14, color = NA) +
  geom_line(linewidth = 0.9) +
  geom_rug(
    data = rug_df,
    aes(x = response_time_seconds, y = NULL, color = question_type),
    sides = "b",
    alpha = 0.18,
    inherit.aes = FALSE
  ) +
  facet_wrap(~ course) +
  scale_y_continuous(limits = c(0, 1), labels = scales::percent_format(accuracy = 1)) +
  labs(
    x = "Response time (seconds)",
    y = "Predicted probability of correct response",
    color = "Question type",
    fill = "Question type"
  ) +
  theme_bw(base_size = 10) +
  theme(legend.position = "bottom", panel.grid.minor = element_blank())

ggsave("outputs/figures/fig3_predicted_correctness_v2.pdf", p, width = 7.2, height = 4.6)
ggsave("outputs/figures/fig3_predicted_correctness_v2.png", p, width = 7.2, height = 4.6, dpi = 300)

print("SPEC 2 model validation outputs written.")
