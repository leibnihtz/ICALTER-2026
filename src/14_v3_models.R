# ICALTER v3 — Parte B: modelos (B1, B2, B4), figuras (B5) y results_summary_v3.json.
# Sigue ANALYSIS_PLAN_v3.md (commit 0e9131c). Lee outputs/validation/analysis_v3.csv y
# outputs/v3/descriptives_v3.json (ambos de 13_v3_prepare.py).
options(warn = 1)
set.seed(20261020)
if (nzchar(Sys.getenv("R_LIBS_USER"))) .libPaths(c(Sys.getenv("R_LIBS_USER"), .libPaths()))
suppressPackageStartupMessages({
  library(lme4); library(dplyr); library(readr); library(jsonlite); library(ggplot2); library(tidyr)
})
dir.create("outputs/v3/models", recursive = TRUE, showWarnings = FALSE)
dir.create("figures", showWarnings = FALSE)

prep <- function(d) {
  d %>% mutate(
    question_type = relevel(factor(question_type), ref = "SingleChoice"),
    course = factor(course), term = factor(term),
    student_id = factor(student_id), question_id = factor(question_id), concept = factor(concept),
    z = as.numeric(scale(log1p(response_time_seconds)))
  )
}
full <- read_csv("outputs/validation/analysis_v3.csv", show_col_types = FALSE)
df <- prep(filter(full, !key_excluded))
desc <- fromJSON("outputs/v3/descriptives_v3.json", simplifyVector = FALSE)

RE <- "(1 | student_id) + (1 | question_id)"
f <- function(fixed, re = RE) as.formula(paste("correct ~", fixed, "+", re))

conv_ok <- function(m) is.null(m@optinfo$conv$lme4$messages)
fit <- function(formula, data) {
  m <- glmer(formula, data, binomial,
             control = glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 2e5)))
  if (!conv_ok(m)) {  # plan §4: un único reintento con Nelder_Mead
    m2 <- glmer(formula, data, binomial,
                control = glmerControl(optimizer = "Nelder_Mead", optCtrl = list(maxfun = 2e5)))
    attr(m2, "optimizer") <- "Nelder_Mead"
    return(m2)
  }
  attr(m, "optimizer") <- "bobyqa"
  m
}

or_row <- function(m, term) {
  b <- fixef(m); if (!term %in% names(b)) return(NULL)
  se <- sqrt(diag(vcov(m)))[[term]]
  p <- 2 * pnorm(-abs(b[[term]] / se))
  list(term = term, log_odds = b[[term]], se = se, p_value = p, odds_ratio = exp(b[[term]]),
       CI95_lower = exp(b[[term]] - qnorm(0.975) * se), CI95_upper = exp(b[[term]] + qnorm(0.975) * se))
}
key_terms <- c(SC_slope = "z",
               TF_x_RT = "z:question_typeTrueFalse",
               MC_x_RT = "z:question_typeMultipleChoice")
summ <- function(m) {
  list(optimizer = attr(m, "optimizer"), converged = conv_ok(m),
       convergence_message = if (conv_ok(m)) NULL else paste(m@optinfo$conv$lme4$messages, collapse = "; "),
       singular = isSingular(m, tol = 1e-4), AIC = AIC(m), BIC = BIC(m),
       logLik = as.numeric(logLik(m)), n = nobs(m),
       students = nlevels(droplevels(m@frame$student_id)),
       questions = nlevels(droplevels(m@frame$question_id)),
       effects = lapply(key_terms, function(t) or_row(m, t)))
}
lrt <- function(a, b) {
  t <- anova(a, b)
  list(chisq = t$Chisq[2], df = t$Df[2], p_value = t$`Pr(>Chisq)`[2], delta_AIC = AIC(b) - AIC(a))
}
write_coef <- function(m, name) {
  b <- fixef(m)
  rows <- bind_rows(lapply(names(b), function(t) as_tibble(or_row(m, t))))
  write_csv(rows, file.path("outputs/v3/models", paste0(name, "_coefficients.csv")))
}

# ---- B1: RQ1 ------------------------------------------------------------
M <- list()
M$M1 <- fit(f("z + question_type + course + term"), df)
M$M2 <- fit(f("z * question_type + course + term"), df)
M$M3_course <- fit(f("z * question_type * course + term"), df)
M$M3_term <- fit(f("z * question_type * term + course"), df)
by_term <- lapply(split(df, df$term), function(d) {
  d <- prep(d %>% mutate(across(where(is.factor), as.character)))
  summ(fit(f("z * question_type + course"), d))
})

# ---- B2: RQ2 ------------------------------------------------------------
M$M4 <- fit(f("z * question_type + course + term", paste(RE, "+ (1 | concept)")), df)
M$M5 <- fit(f("z * question_type + course + term", paste(RE, "+ (1 + z | concept)")), df)
vc5 <- as.data.frame(VarCorr(M$M5))
sd_slope <- vc5$sdcor[vc5$grp == "concept" & vc5$var1 == "z" & is.na(vc5$var2)]
sd_int_m4 <- as.data.frame(VarCorr(M$M4)) %>% filter(grp == "concept") %>% pull(sdcor)

# ---- B4: robustez ---------------------------------------------------------
R <- list()
R$uncorrected_labels <- summ(fit(f("z * question_type + course + term"), prep(full)))
d1 <- prep(filter(full, !key_excluded, term == "2026-1"))
R$term_2026_1_only <- summ(fit(f("z * question_type + course"), d1))
p99 <- quantile(df$response_time_seconds, 0.99)
R$p99_trim <- summ(fit(f("z * question_type + course + term"),
                       prep(filter(full, !key_excluded, response_time_seconds <= p99))))
R$p99_trim$p99_seconds <- unname(p99)
R$random_slope_question <- tryCatch(
  summ(fit(f("z * question_type + course + term", "(1 | student_id) + (1 + z | question_id)"), df)),
  error = function(e) list(error = conditionMessage(e)))

for (n in names(M)) write_coef(M[[n]], n)

# ---- Escenario RQ2 (plan §5) --------------------------------------------
tf_excl1 <- function(m) { e <- or_row(m, key_terms[["TF_x_RT"]]); e$CI95_lower > 1 || e$CI95_upper < 1 }
same_dir <- function(m) sign(fixef(m)[[key_terms[["TF_x_RT"]]]]) == sign(fixef(M$M2)[[key_terms[["TF_x_RT"]]]])
m5_usable <- conv_ok(M$M5) && !isSingular(M$M5, tol = 1e-4)
lrt54 <- lrt(M$M4, M$M5)
holds <- tf_excl1(M$M4) && same_dir(M$M4) && (!m5_usable || (tf_excl1(M$M5) && same_dir(M$M5)))
scenario <- if (!holds) 3L else if (m5_usable && lrt54$p_value < 0.05) 2L else 1L
scenario_text <- c("format effect holds within concept",
                   "format effect holds and RT-accuracy association varies across concepts",
                   "format effect disappears after controlling for concept")[scenario]

# ---- B5: figuras ------------------------------------------------------------
fmt_lab <- c(SingleChoice = "Single choice", TrueFalse = "True/false", MultipleChoice = "Multiple choice")
bands <- read_csv("outputs/v3/tables/rt_bands_v3.csv", show_col_types = FALSE) %>%
  mutate(rt_band = factor(rt_band, levels = c("0-<10", "10-<20", "20-<30", "30-<45", "45-<60", "60+")),
         question_type = factor(fmt_lab[question_type], levels = fmt_lab))
p1 <- ggplot(bands, aes(rt_band, accuracy, colour = question_type, group = question_type)) +
  geom_line() + geom_point(aes(size = n)) +
  scale_x_discrete(labels = c("<10", "10–20", "20–30", "30–45", "45–60", "60+")) +
  scale_y_continuous(labels = scales::percent, limits = c(0, 1)) + scale_size_area(max_size = 3, guide = "none") +
  labs(x = "Response time band (s)", y = "Accuracy", colour = NULL) +
  theme_bw(base_size = 9) + theme(legend.position = "bottom", legend.margin = margin(0, 0, 0, 0))
ggsave("figures/fig1_accuracy_rt_bands_v3.pdf", p1, width = 3.5, height = 2.6, device = "pdf")

# Probabilidad predicha (efectos fijos) promediando el predictor lineal sobre la mezcla curso × término.
mu <- attr(scale(log1p(df$response_time_seconds)), "scaled:center")
sdv <- attr(scale(log1p(df$response_time_seconds)), "scaled:scale")
mix <- count(df, course, term) %>% mutate(w = n / sum(n))
b <- fixef(M$M2); V <- vcov(M$M2)
pred <- bind_rows(lapply(levels(df$question_type), function(qt) {
  rng <- quantile(df$response_time_seconds[df$question_type == qt], c(0.05, 0.95))
  secs <- seq(rng[1], rng[2], length.out = 60)
  bind_rows(lapply(secs, function(s) {
    nd <- mutate(mix, z = (log1p(s) - mu) / sdv,
                 question_type = factor(qt, levels = levels(df$question_type)), correct = 0L)
    X <- model.matrix(~ z * question_type + course + term, nd)
    x <- colSums(X * nd$w)
    eta <- sum(x * b); se <- sqrt(drop(t(x) %*% V %*% x))
    tibble(question_type = qt, seconds = s, p = plogis(eta),
           lo = plogis(eta - 1.96 * se), hi = plogis(eta + 1.96 * se))
  }))
})) %>% mutate(question_type = factor(fmt_lab[question_type], levels = fmt_lab))
p2 <- ggplot(pred, aes(seconds, p, colour = question_type, fill = question_type)) +
  geom_ribbon(aes(ymin = lo, ymax = hi), alpha = 0.15, colour = NA) + geom_line() +
  scale_y_continuous(labels = scales::percent, limits = c(0, 1)) +
  labs(x = "Response time (s), P5–P95 per format", y = "Predicted P(correct), M2",
       colour = NULL, fill = NULL) +
  theme_bw(base_size = 9) + theme(legend.position = "bottom", legend.margin = margin(0, 0, 0, 0))
ggsave("figures/fig2_predicted_m2_v3.pdf", p2, width = 3.5, height = 2.6, device = "pdf")

fig3 <- FALSE
if (m5_usable) {
  re <- ranef(M$M5, condVar = TRUE)$concept
  pv <- attr(re, "postVar")
  dom <- df %>% count(concept, question_type) %>% group_by(concept) %>% slice_max(n, n = 1, with_ties = FALSE)
  blup <- tibble(concept = rownames(re), dev = re$z, se = sqrt(pv[2, 2, ])) %>%
    mutate(slope = fixef(M$M5)[["z"]] + dev) %>%
    left_join(dom %>% transmute(concept = as.character(concept), dominant = fmt_lab[as.character(question_type)]),
              by = "concept") %>%
    arrange(slope) %>% mutate(idx = row_number())
  p3 <- ggplot(blup, aes(slope, idx, colour = dominant)) +
    geom_vline(xintercept = 0, linetype = 2) +
    geom_errorbarh(aes(xmin = slope - 1.96 * se, xmax = slope + 1.96 * se), height = 0) + geom_point() +
    labs(x = "RT slope by concept (SC reference, log-odds per SD)", y = "Concept", colour = "Dominant format") +
    theme_bw(base_size = 9) + theme(axis.text.y = element_blank(), axis.ticks.y = element_blank())
  ggsave("figures/fig3_concept_slopes_v3.pdf", p3, width = 3.5, height = 3.2, device = "pdf")
  fig3 <- TRUE
}

# ---- results_summary_v3.json -------------------------------------------
res <- list(
  plan_commit = "0e9131c",
  dataset = desc$n_primary, inclusion_flow = desc$flow,
  rt_transform = list(log1p_mean = mu, log1p_sd = sdv),
  B1 = list(
    M1 = summ(M$M1), M2 = summ(M$M2),
    LRT_M2_vs_M1 = lrt(M$M1, M$M2),
    M3_course = summ(M$M3_course), LRT_M3course_vs_M2 = lrt(M$M2, M$M3_course),
    M3_term = summ(M$M3_term), LRT_M3term_vs_M2 = lrt(M$M2, M$M3_term),
    M2_by_term = by_term
  ),
  B2 = list(
    M4 = summ(M$M4), M5 = summ(M$M5), LRT_M5_vs_M4 = lrt54,
    M4_concept_intercept_sd = sd_int_m4, M5_concept_slope_sd = sd_slope,
    abs_log_or_TF_x_RT_M2 = abs(fixef(M$M2)[[key_terms[["TF_x_RT"]]]]),
    M5_usable = m5_usable,
    scenario = scenario, scenario_text = scenario_text
  ),
  B3 = list(SC_vs_TF = desc$b3_SC_vs_TF, SC_vs_MC = desc$b3_SC_vs_MC),
  B4 = c(R, list(run_level_direction = desc$run_level_direction)),
  B5 = list(fig1 = "figures/fig1_accuracy_rt_bands_v3.pdf", fig2 = "figures/fig2_predicted_m2_v3.pdf",
            fig3 = if (fig3) "figures/fig3_concept_slopes_v3.pdf" else NULL),
  rt_support = desc$rt_support,
  generated_by = "src/14_v3_models.R",
  R_version = R.version.string, lme4_version = as.character(packageVersion("lme4"))
)
write_json(res, "outputs/results_summary_v3.json", auto_unbox = TRUE, digits = 10, pretty = TRUE, null = "null")
cat("scenario:", scenario, "-", scenario_text, "\n")
