from __future__ import annotations

import matplotlib.pyplot as plt
import seaborn as sns

from common import FIGURES, ensure_dirs, load_analysis_data


def save_figure(fig, stem: str) -> None:
    fig.savefig(FIGURES / f"{stem}.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIGURES / f"{stem}.pdf", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    ensure_dirs()
    df = load_analysis_data(include_timestamp_invalid=False)
    sns.set_theme(style="whitegrid", context="paper", font_scale=1.15)
    palette = {
        "SingleChoice": "#2B6CB0",
        "MultipleChoice": "#2F855A",
        "TrueFalse": "#B7791F",
        "Correct": "#2F855A",
        "Incorrect": "#A23B3B",
    }

    fig1 = sns.catplot(
        data=df,
        x="question_type",
        y="response_time_seconds",
        hue="question_type",
        col="course",
        kind="violin",
        inner="box",
        cut=0,
        linewidth=0.9,
        palette=palette,
        height=4,
        aspect=1.05,
        sharey=True,
        legend=False,
    )
    fig1.set_axis_labels("Question type", "Response time (seconds)")
    fig1.set_titles("{col_name}")
    for ax in fig1.axes.flat:
        ax.tick_params(axis="x", rotation=20)
    save_figure(fig1.figure, "fig1_response_time_distribution")

    fig2 = sns.catplot(
        data=df,
        x="correctness",
        y="response_time_seconds",
        col="question_type",
        row="course",
        kind="box",
        hue="correctness",
        palette=palette,
        height=3.1,
        aspect=1,
        showfliers=False,
        legend=False,
    )
    fig2.set_axis_labels("", "Response time (seconds)")
    fig2.set_titles("{row_name} | {col_name}")
    save_figure(fig2.figure, "fig2_correctness_response_time")

    session = df.groupby(["course", "session_id"]).agg(
        session_started_at=("session_started_at", "min"),
        participating_students=("student_id_hash", "nunique"),
        responses=("correct", "size"),
        accuracy=("correct", "mean"),
        median_response_time=("response_time_seconds", "median"),
    )
    session = session.reset_index().sort_values(["course", "session_started_at"])
    session["session_index"] = session.groupby("course").cumcount() + 1

    fig, ax1 = plt.subplots(figsize=(7.2, 4.2))
    for course, subset in session.groupby("course"):
        ax1.plot(subset["session_index"], subset["accuracy"], marker="o", label=f"{course} accuracy")
    ax1.set_xlabel("Session index")
    ax1.set_ylabel("Accuracy")
    ax1.set_ylim(0, 1)
    ax1.legend(frameon=False, loc="best")
    sns.despine(fig=fig)
    save_figure(fig, "fig4_session_evolution")

    print("Response-time figures written.")


if __name__ == "__main__":
    main()
