# ICALTER v3 — reproduce the main results from the PUBLIC dataset only.
# Reads data/public_v3/leibtimeter_public_v3.csv, fits M1, M2 (primary) and M4, and
# compares them with outputs/results_summary_v3.json. No private file is needed.
#   Rscript src/18_v3_reproduce_from_public.R
options(warn = 1)
if (nzchar(Sys.getenv("R_LIBS_USER"))) .libPaths(c(Sys.getenv("R_LIBS_USER"), .libPaths()))
suppressPackageStartupMessages({ library(lme4); library(dplyr); library(readr); library(jsonlite) })

d <- read_csv("data/public_v3/leibtimeter_public_v3.csv", show_col_types = FALSE) %>%
  filter(key_excluded == 0) %>%                      # ANALYSIS_PLAN_v3.md §2.3
  mutate(question_type = relevel(factor(question_type), ref = "SingleChoice"),
         course = factor(course), term = factor(term),
         z = as.numeric(scale(log1p(response_time_seconds))))

ctrl <- glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 2e5))
re <- "+ (1 | student_id) + (1 | question_id)"
fit <- function(fx) glmer(as.formula(paste("is_correct ~", fx, re)), d, binomial, control = ctrl)
m1 <- fit("z + question_type + course + term")
m2 <- fit("z * question_type + course + term")
m4 <- fit("z * question_type + course + term + (1 | concept_id)")

ref <- fromJSON("outputs/results_summary_v3.json")
terms <- c(SC_slope = "z", TF_x_RT = "z:question_typeTrueFalse", MC_x_RT = "z:question_typeMultipleChoice")
show <- function(name, m, r) {
  for (k in names(terms)) {
    b <- fixef(m)[[terms[[k]]]]; se <- sqrt(vcov(m)[terms[[k]], terms[[k]]])
    cat(sprintf("%-3s %-9s OR %.3f [%.3f, %.3f]   reported OR %.3f\n", name, k, exp(b),
                exp(b - 1.959964 * se), exp(b + 1.959964 * se), r$effects[[k]]$odds_ratio))
  }
}
cat(sprintf("n = %d responses, %d students, %d questions, %d concepts\n", nobs(m2),
            n_distinct(d$student_id), n_distinct(d$question_id), n_distinct(d$concept_id)))
show("M2", m2, ref$B1$M2)
show("M4", m4, ref$B2$M4)
t <- anova(m1, m2)
cat(sprintf("LRT M2 vs M1: chisq(%d) = %.3f, p = %.3g   reported chisq %.3f\n",
            t$Df[2], t$Chisq[2], t$`Pr(>Chisq)`[2], ref$B1$LRT_M2_vs_M1$chisq))
ok <- abs(AIC(m2) - ref$B1$M2$AIC) < 1e-6 && abs(AIC(m4) - ref$B2$M4$AIC) < 1e-6 &&
  abs(t$Chisq[2] - ref$B1$LRT_M2_vs_M1$chisq) < 1e-6
cat("Matches results_summary_v3.json:", ok, "\n")
