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

fit_glmm <- function(formula, data) {
  glmer(
    formula,
    data = data,
    family = binomial(link = "logit"),
    control = glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 2e5))
  )
}

models <- list()
model_formulas <- list(
  M0 = correct ~ 1 + (1 | student_id_hash) + (1 | question_id),
  M1 = correct ~ z_log_response_time + course + question_type +
    (1 | student_id_hash) + (1 | question_id),
  M2 = correct ~ z_log_response_time * question_type + course +
    (1 | student_id_hash) + (1 | question_id),
  M3 = correct ~ z_log_response_time * question_type * course +
    (1 | student_id_hash) + (1 | question_id)
)

models$M0 <- fit_glmm(model_formulas$M0, df)
models$M1 <- fit_glmm(model_formulas$M1, df)
models$M2 <- fit_glmm(model_formulas$M2, df)

m3_error <- NA_character_
models["M3"] <- list(tryCatch(
  fit_glmm(model_formulas$M3, df),
  error = function(e) {
    m3_error <<- conditionMessage(e)
    NULL
  }
))

diagnostics <- bind_rows(lapply(names(model_formulas), function(name) {
  model_obj <- models[[name]]
  if (is.null(model_obj)) {
    return(tibble(
      model = name,
      formula = paste(deparse(model_formulas[[name]]), collapse = " "),
      converged = FALSE,
      convergence_message = m3_error,
      singular = NA,
      AIC = NA_real_,
      BIC = NA_real_,
      log_likelihood = NA_real_,
      n_observations = nrow(df),
      n_students = n_distinct(df$student_id_hash),
      n_questions = n_distinct(df$question_id)
    ))
  }
  messages <- model_obj@optinfo$conv$lme4$messages
  tibble(
    model = name,
    formula = paste(deparse(model_formulas[[name]]), collapse = " "),
    converged = is.null(messages),
    convergence_message = ifelse(is.null(messages), NA_character_, paste(messages, collapse = "; ")),
    singular = isSingular(model_obj, tol = 1e-4),
    AIC = AIC(model_obj),
    BIC = BIC(model_obj),
    log_likelihood = as.numeric(logLik(model_obj)),
    n_observations = nobs(model_obj),
    n_students = n_distinct(model_obj@frame$student_id_hash),
    n_questions = n_distinct(model_obj@frame$question_id)
  )
}))
write_csv(diagnostics, "outputs/models/model_diagnostics.csv")

write_coefficients <- function(model, path) {
  if (is.null(model)) {
    write_csv(tibble(), path)
    return(invisible(NULL))
  }
  out <- tidy(model, effects = "fixed", conf.int = TRUE, conf.method = "Wald") %>%
    transmute(
      term,
      estimate_log_odds = estimate,
      standard_error = std.error,
      z_value = statistic,
      p_value = p.value,
      odds_ratio = exp(estimate),
      CI95_lower = exp(conf.low),
      CI95_upper = exp(conf.high)
    )
  write_csv(out, path)
}

write_coefficients(models$M1, "outputs/models/M1_coefficients.csv")
write_coefficients(models$M2, "outputs/models/M2_coefficients.csv")
write_coefficients(models$M3, "outputs/models/M3_coefficients.csv")

rt_grid <- c(5, 10, 20, 30, 45, 60)
log_mean <- mean(log1p(df$response_time_seconds), na.rm = TRUE)
log_sd <- sd(log1p(df$response_time_seconds), na.rm = TRUE)
pred_grid <- expand_grid(
  response_time_seconds = rt_grid,
  question_type = levels(df$question_type),
  course = levels(df$course)
) %>%
  mutate(
    question_type = factor(question_type, levels = levels(df$question_type)),
    course = factor(course, levels = levels(df$course)),
    z_log_response_time = (log1p(response_time_seconds) - log_mean) / log_sd,
    student_id_hash = df$student_id_hash[1],
    question_id = df$question_id[1]
  )

fixed_link <- function(model_obj, newdata) {
  tt <- delete.response(terms(model_obj, fixed.only = TRUE))
  X <- model.matrix(tt, newdata)
  beta <- fixef(model_obj)
  X <- X[, names(beta), drop = FALSE]
  fit <- as.vector(X %*% beta)
  se <- sqrt(diag(X %*% as.matrix(vcov(model_obj)) %*% t(X)))
  list(fit = fit, se.fit = se)
}

pred_link <- fixed_link(models$M2, pred_grid)
predictions <- pred_grid %>%
  mutate(
    fit_link = pred_link$fit,
    se_link = pred_link$se.fit,
    predicted_probability = plogis(fit_link),
    CI95_lower = plogis(fit_link - 1.96 * se_link),
    CI95_upper = plogis(fit_link + 1.96 * se_link)
  ) %>%
  select(course, question_type, response_time_seconds, z_log_response_time,
         predicted_probability, CI95_lower, CI95_upper)
write_csv(predictions, "outputs/models/M2_predicted_probabilities.csv")

plot_grid <- expand_grid(
  response_time_seconds = seq(
    quantile(df$response_time_seconds, 0.01, na.rm = TRUE),
    quantile(df$response_time_seconds, 0.99, na.rm = TRUE),
    length.out = 120
  ),
  question_type = levels(df$question_type),
  course = levels(df$course)
) %>%
  mutate(
    question_type = factor(question_type, levels = levels(df$question_type)),
    course = factor(course, levels = levels(df$course)),
    z_log_response_time = (log1p(response_time_seconds) - log_mean) / log_sd,
    student_id_hash = df$student_id_hash[1],
    question_id = df$question_id[1]
  )
plot_link <- fixed_link(models$M2, plot_grid)
plot_df <- plot_grid %>%
  mutate(
    fit_link = plot_link$fit,
    se_link = plot_link$se.fit,
    predicted_probability = plogis(fit_link),
    CI95_lower = plogis(fit_link - 1.96 * se_link),
    CI95_upper = plogis(fit_link + 1.96 * se_link)
  )

p <- ggplot(plot_df, aes(x = response_time_seconds, y = predicted_probability,
                         color = question_type, fill = question_type)) +
  geom_ribbon(aes(ymin = CI95_lower, ymax = CI95_upper), alpha = 0.16, color = NA) +
  geom_line(linewidth = 0.9) +
  facet_wrap(~ course) +
  scale_y_continuous(limits = c(0, 1), labels = scales::percent_format(accuracy = 1)) +
  labs(x = "Response time (seconds)", y = "Predicted probability of correct response",
       color = "Question type", fill = "Question type") +
  theme_bw(base_size = 10) +
  theme(legend.position = "bottom", panel.grid.minor = element_blank())
ggsave("outputs/figures/fig3_predicted_correctness.pdf", p, width = 7.2, height = 4.6)
ggsave("outputs/figures/fig3_predicted_correctness.png", p, width = 7.2, height = 4.6, dpi = 300)

saveRDS(models, "outputs/models/glmm_models.rds")
print("GLMM model outputs written.")
