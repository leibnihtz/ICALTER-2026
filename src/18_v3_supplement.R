# Post-freeze supplement. Run from repository root:
# Rscript src/18_v3_supplement.R
# Reads the frozen raw private extraction and public CSV; writes only the supplement.
# Derived from Codex's audit/review_format_slopes.R. Never updates the v3 freeze.
options(warn = 1)
.libPaths(c(Sys.getenv("R_LIBS_USER"), ".r-lib", .libPaths()))
suppressPackageStartupMessages({
  library(lme4); library(dplyr); library(readr); library(jsonlite)
})
summary_path <- "outputs/results_summary_v3.json"
public_path <- "data/public_v3/leibtimeter_public_v3.csv"
private_path <- "data/private_v3/q4_responses.csv"
output_path <- "outputs/results_supplement_v3_1.json"
tag <- "v3.0-paper-freeze"
git <- function(...) {
  ans <- system2("git", c(...), stdout = TRUE)
  if (!is.null(attr(ans, "status"))) stop("Git provenance check failed")
  trimws(ans)
}
tag_before <- git("rev-parse", paste0("refs/tags/", tag))
summary_before <- unname(tools::md5sum(summary_path))
for (path in c(summary_path, public_path)) {
  stopifnot(identical(git("hash-object", path), git("rev-parse", paste0(tag, ":", path))))
}
tbool <- function(x) tolower(as.character(x)) %in% c("t", "true", "1")
# Same inclusion rules as src/13_v3_prepare.py; rebuild in memory from private_v3.
raw <- read_csv(private_path, col_types = cols(.default = col_character()), show_col_types = FALSE)
excluded <- c("6ddc4a8fe7344ce2a5ca8db88b6b3059", "2e64446487175f3693326d8f374f7e3b",
              "9a5b071450869af1f0062e4614e96799", "de74a3c0ac677254023f518cf74187b2",
              "d3000ecafb2f9cecf2b43909743ae211")
raw <- raw %>% mutate(across(c(OpenedAt, ClosedAt, SubmittedAt), parse_datetime))
stopifnot(!any(problems(raw)$row))
full_private <- raw %>%
  filter(tbool(evaluable), SubmittedAt < as.POSIXct("2026-10-17", tz = "UTC"),
         !is.na(OpenedAt), !is.na(ClosedAt), SubmittedAt >= OpenedAt, SubmittedAt <= ClosedAt) %>%
  transmute(student_id, question_id, run_id, course = toupper(trimws(course_name)), term,
            question_type = QuestionType, response_time_seconds = parse_double(rt_seconds),
            correct = as.integer(tbool(IsCorrect)), key_excluded = question_id %in% excluded) %>%
  arrange(student_id, run_id)
full_public <- read_csv(public_path, show_col_types = FALSE) %>%
  transmute(student_id, question_id, run_id, course, term, question_type,
            response_time_seconds, correct = as.integer(is_correct), key_excluded = key_excluded == 1) %>%
  arrange(student_id, run_id)
analytic <- c("course", "term", "question_type", "response_time_seconds", "correct", "key_excluded")
stopifnot(nrow(full_private) == 3227L, nrow(full_public) == 3227L,
          identical(as.data.frame(full_private[analytic]), as.data.frame(full_public[analytic])))
prep <- function(d) d %>% mutate(
  question_type = relevel(factor(question_type), "SingleChoice"),
  course = factor(course), term = factor(term), student_id = factor(student_id),
  question_id = factor(question_id), z = as.numeric(scale(log1p(response_time_seconds))))
private <- prep(filter(full_private, !key_excluded))
public <- prep(filter(full_public, !key_excluded))
fit <- function(d) {
  formula <- correct ~ z * question_type + course + term + (1 | student_id) + (1 | question_id)
  m <- glmer(formula, d, binomial,
             control = glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 2e5)))
  if (!is.null(m@optinfo$conv$lme4$messages)) {
    m <- glmer(formula, d, binomial,
               control = glmerControl(optimizer = "Nelder_Mead", optCtrl = list(maxfun = 2e5)))
  }
  stopifnot(is.null(m@optinfo$conv$lme4$messages), !isSingular(m, tol = 1e-4))
  m
}
m_private <- fit(private)
m_public <- fit(public)
delta_coef <- max(abs(fixef(m_private) - fixef(m_public)))
delta_vcov <- max(abs(as.matrix(vcov(m_private)) - as.matrix(vcov(m_public))))
delta_aic <- abs(AIC(m_private) - AIC(m_public))
delta_ll <- abs(as.numeric(logLik(m_private)) - as.numeric(logLik(m_public)))
exact_equal <- all(c(delta_coef, delta_vcov, delta_aic, delta_ll) == 0)
contrast <- function(m, fmt) {
  b <- fixef(m); V <- as.matrix(vcov(m))
  L <- setNames(rep(0, length(b)), names(b)); L["z"] <- 1
  interaction <- paste0("z:question_type", fmt)
  L[interaction] <- 1
  est <- sum(L * b); se <- sqrt(drop(t(L) %*% V %*% L))
  list(log_odds = est, se = se, odds_ratio = exp(est),
       CI95_lower = exp(est - qnorm(.975) * se), CI95_upper = exp(est + qnorm(.975) * se),
       covariance_SC_interaction = unname(V["z", interaction]))
}
slopes <- list(TF = contrast(m_private, "TrueFalse"), MC = contrast(m_private, "MultipleChoice"))
block <- function(d) list(responses = nrow(d), students = n_distinct(d$student_id),
                         questions = n_distinct(d$question_id))
offering <- function(course_name, term_name) block(filter(private, course == course_name, term == term_name))
offerings <- list(`BD-1` = offering("BIG DATA", "2026-1"), `RII-1` = offering("REDES II", "2026-1"),
                  `BD-2` = offering("BIG DATA", "2026-2"), `RII-2` = offering("REDES II", "2026-2"))
terms <- lapply(split(private, private$term), block)
total <- block(private)
expected_counts <- list(`BD-1` = c(32, 30), `RII-1` = c(24, 34), `BD-2` = c(39, 31), `RII-2` = c(36, 40))
counts_ok <- all(vapply(names(offerings), function(k)
  all(unlist(offerings[[k]][c("students", "questions")]) == expected_counts[[k]]), logical(1)))
terms_ok <- all(unlist(terms[["2026-1"]][c("students", "questions")]) == c(56, 64)) &&
  all(unlist(terms[["2026-2"]][c("students", "questions")]) == c(75, 71)) &&
  offerings[["BD-1"]]$students + offerings[["RII-1"]]$students == terms[["2026-1"]]$students &&
  offerings[["BD-1"]]$questions + offerings[["RII-1"]]$questions == terms[["2026-1"]]$questions &&
  offerings[["BD-2"]]$students + offerings[["RII-2"]]$students == terms[["2026-2"]]$students &&
  offerings[["BD-2"]]$questions + offerings[["RII-2"]]$questions == terms[["2026-2"]]$questions
total_ok <- total$students == 130L && total$questions == 135L
expected_slopes <- list(TF = c(1.43, 1.11, 1.85), MC = c(1.13, .85, 1.50))
rounded_ok <- all(vapply(names(slopes), function(k)
  all(round(unlist(slopes[[k]][c("odds_ratio", "CI95_lower", "CI95_upper")]), 2) == expected_slopes[[k]]), logical(1)))
p99 <- unname(quantile(private$response_time_seconds, .99))
scaling <- function(full) {
  primary <- filter(full, !key_excluded)
  samples <- list(pooled = primary, `2026-1` = filter(primary, term == "2026-1"),
                  `2026-2` = filter(primary, term == "2026-2"),
                  p99_trim = filter(primary, response_time_seconds <= p99), uncorrected_labels = full)
  lapply(samples, function(d) {
    x <- log1p(d$response_time_seconds)
    list(n = nrow(d), log1p_mean = mean(x), log1p_sd = sd(x))
  })
}
scales_private <- scaling(full_private)
scales_public <- scaling(full_public)
scales_equal <- identical(scales_private, scales_public)
frozen_unchanged <- identical(summary_before, unname(tools::md5sum(summary_path))) &&
  identical(tag_before, git("rev-parse", paste0("refs/tags/", tag)))
checks <- list(private_public_M2_exact = exact_equal, rounded_slopes_expected = rounded_ok,
               offering_counts_expected = counts_ok, term_sums_expected = terms_ok,
               unique_total_expected = total_ok, private_public_scaling_equal = scales_equal,
               frozen_artifacts_unchanged = frozen_unchanged)
differences <- names(checks)[!unlist(checks)]
out <- list(
  note = "post-freeze supplement; derived from the frozen v3 data and model",
  provenance = list(script = "src/18_v3_supplement.R", freeze_tag = tag,
                    freeze_commit = git("rev-list", "-n", "1", tag),
                    private_input = private_path, public_input = public_path,
                    input_md5 = as.list(tools::md5sum(c(private_path, public_path))),
                    frozen_summary_md5 = summary_before,
                    R_version = R.version.string, lme4_version = as.character(packageVersion("lme4"))),
  M2_comparison = list(n_private = nobs(m_private), n_public = nobs(m_public),
                       max_abs_coef_diff = delta_coef, max_abs_vcov_diff = delta_vcov,
                       aic_diff = delta_aic, loglik_diff = delta_ll,
                       both_converged = TRUE, both_nonsingular = TRUE),
  format_slopes = slopes,
  offerings = offerings, by_term = terms, total_unique = total,
  students_in_both_terms = length(intersect(filter(private, term == "2026-1")$student_id,
                                           filter(private, term == "2026-2")$student_id)),
  standardization = scales_private, p99_cutoff_seconds = p99,
  checks = checks, differences = unname(as.list(differences)))
dir.create(dirname(output_path), showWarnings = FALSE, recursive = TRUE)
write_json(out, output_path, auto_unbox = TRUE, pretty = TRUE, digits = NA, null = "null")
cat("Supplement written:", output_path, "\n")
if (length(differences)) stop("Differences detected: ", paste(differences, collapse = ", "))
cat("All checks passed; private/public M2 delta = 0; expected rounded values confirmed.\n")
