"""
PHASE 7: Bias Detection (Additional Point from the brief)

Checks whether the ranking model's scores differ systematically across
a sensitive attribute group. For a portfolio project, the simplest
honest approach is checking disparity across a self-reported or
inferred grouping (e.g. gender-associated first names) -- clearly
document this as a heuristic, not a ground-truth label, in your report.

Uses Fairlearn's MetricFrame to compute group-wise mean scores and a
demographic parity difference metric.
"""
import pandas as pd
from fairlearn.metrics import MetricFrame, demographic_parity_difference


def check_score_disparity(df: pd.DataFrame, score_col: str, group_col: str):
    """
    df: DataFrame with at least [score_col, group_col]
    group_col: e.g. inferred gender group, or graduation-year bucket (age proxy)
    """
    mf = MetricFrame(
        metrics={"mean_score": lambda y_true, y_pred: y_pred.mean()},
        y_true=df[score_col],       # placeholder, not used by mean_score
        y_pred=df[score_col],
        sensitive_features=df[group_col],
    )
    print("Group-wise mean scores:")
    print(mf.by_group)

    # Binarize scores at median to compute demographic parity difference
    threshold = df[score_col].median()
    binary_scores = (df[score_col] >= threshold).astype(int)

    dpd = demographic_parity_difference(
        y_true=binary_scores,       # required arg, treated as reference
        y_pred=binary_scores,
        sensitive_features=df[group_col],
    )
    print(f"\nDemographic parity difference (shortlist rate gap): {dpd:.4f}")
    print("A value near 0 means groups are shortlisted at similar rates.")
    return mf, dpd


if __name__ == "__main__":
    # Example synthetic run
    import numpy as np
    np.random.seed(0)
    df = pd.DataFrame({
        "final_rank_score": np.random.uniform(0, 1, 100),
        "inferred_group": np.random.choice(["A", "B"], 100),
    })
    check_score_disparity(df, score_col="final_rank_score", group_col="inferred_group")
