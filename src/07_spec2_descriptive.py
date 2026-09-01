from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from common import FIGURES, TABLES, ensure_dirs, load_analysis_data


BAND_LABELS = ["0-<10", "10-<20", "20-<30", "30-<45", "45-<60", "60+"]
BAND_EDGES = [0, 10, 20, 30, 45, 60, np.inf]


def main() -> None:
    ensure_dirs()
    df = load_analysis_data(include_timestamp_invalid=False)
    df["response_time_band"] = pd.cut(
        df["response_time_seconds"],
        bins=BAND_EDGES,
        labels=BAND_LABELS,
        right=False,
        include_lowest=True,
    )

    bands = (
        df.groupby(["course", "question_type", "response_time_band"], observed=False)
        .agg(
            n=("correct", "size"),
            correct=("correct", "sum"),
            mean_response_time=("response_time_seconds", "mean"),
            median_response_time=("response_time_seconds", "median"),
        )
        .reset_index()
    )
    bands["incorrect"] = bands["n"] - bands["correct"]
    bands["accuracy"] = np.where(bands["n"] > 0, bands["correct"] / bands["n"], np.nan)
    bands = bands[
        [
            "course",
            "question_type",
            "response_time_band",
            "n",
            "correct",
            "incorrect",
            "accuracy",
            "mean_response_time",
            "median_response_time",
        ]
    ]
    bands.to_csv(TABLES / "response_time_bands.csv", index=False)

    overall = (
        df.groupby(["question_type", "response_time_band"], observed=False)
        .agg(n=("correct", "size"), correct=("correct", "sum"))
        .reset_index()
    )
    overall["incorrect"] = overall["n"] - overall["correct"]
    overall["accuracy"] = np.where(overall["n"] > 0, overall["correct"] / overall["n"], np.nan)
    overall[["question_type", "response_time_band", "n", "correct", "incorrect", "accuracy"]].to_csv(
        TABLES / "response_time_bands_overall.csv", index=False
    )

    support = (
        df.groupby("question_type")
        .agg(
            minimum=("response_time_seconds", "min"),
            p5=("response_time_seconds", lambda s: s.quantile(0.05)),
            p25=("response_time_seconds", lambda s: s.quantile(0.25)),
            median=("response_time_seconds", "median"),
            p75=("response_time_seconds", lambda s: s.quantile(0.75)),
            p90=("response_time_seconds", lambda s: s.quantile(0.90)),
            p95=("response_time_seconds", lambda s: s.quantile(0.95)),
            p99=("response_time_seconds", lambda s: s.quantile(0.99)),
            maximum=("response_time_seconds", "max"),
            n=("response_time_seconds", "size"),
        )
        .reset_index()
    )
    support.to_csv(TABLES / "response_time_support.csv", index=False)

    qdiag = pd.read_csv(TABLES / "question_level_diagnostics.csv")
    comparable = qdiag[qdiag["correct_faster"].notna()].copy()
    comparable["correct_faster_bool"] = comparable["correct_faster"].astype(str).str.lower().eq("true")
    comparable["tie_bool"] = False
    direction = (
        comparable.groupby(["course", "question_type"])
        .agg(
            comparable_question_runs=("question_run_id", "nunique"),
            correct_faster_runs=("correct_faster_bool", "sum"),
            ties=("tie_bool", "sum"),
        )
        .reset_index()
    )
    direction["incorrect_faster_runs"] = (
        direction["comparable_question_runs"] - direction["correct_faster_runs"] - direction["ties"]
    )
    direction["percentage_correct_faster"] = np.where(
        direction["comparable_question_runs"] > 0,
        direction["correct_faster_runs"] / direction["comparable_question_runs"] * 100,
        np.nan,
    )
    direction = direction[
        [
            "course",
            "question_type",
            "comparable_question_runs",
            "correct_faster_runs",
            "incorrect_faster_runs",
            "ties",
            "percentage_correct_faster",
        ]
    ]
    direction.to_csv(TABLES / "question_direction_summary.csv", index=False)

    sns.set_theme(style="whitegrid", context="paper", font_scale=1.1)
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.8), sharey=True)
    palette = {
        "SingleChoice": "#2B6CB0",
        "MultipleChoice": "#2F855A",
        "TrueFalse": "#B7791F",
    }
    for ax, (course, subset) in zip(axes, bands.groupby("course", sort=True)):
        plot_data = subset[subset["n"] > 0].copy()
        sns.lineplot(
            data=plot_data,
            x="response_time_band",
            y="accuracy",
            hue="question_type",
            marker="o",
            palette=palette,
            ax=ax,
        )
        ax.set_title(course)
        ax.set_xlabel("Response time band (seconds)")
        ax.set_ylabel("Observed accuracy" if ax is axes[0] else "")
        ax.set_ylim(0, 1)
        ax.tick_params(axis="x", rotation=25)
        ax.legend_.remove()
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False)
    fig.tight_layout(rect=(0, 0.12, 1, 1))
    fig.savefig(FIGURES / "fig4_accuracy_by_time_band.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIGURES / "fig4_accuracy_by_time_band.pdf", bbox_inches="tight")
    plt.close(fig)

    print("SPEC 2 descriptive tables and Figure 4 written.")


if __name__ == "__main__":
    main()
