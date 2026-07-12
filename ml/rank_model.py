"""
PHASE 3b: Candidate Ranking Model

Trains a Gradient Boosting classifier on top of the features from
scoring.py (semantic_similarity, skill_overlap, experience_match)
to predict a final "shortlist score" per candidate.

For a portfolio project without real historical hiring data, you can:
  1. Bootstrap labels using a simple rule (e.g. label=1 if
     semantic_similarity > 0.6 AND skill_overlap > 0.5), OR
  2. Manually label ~50-100 sample candidate/job pairs yourself.

Train this locally first, then register + deploy via Azure ML
(see README Phase 3 notes) so scoring can call a managed endpoint
instead of loading the model inline in the Function.
"""
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib


FEATURE_COLUMNS = ["semantic_similarity", "skill_overlap", "experience_match"]


def train(data_path: str, model_out_path: str = "rank_model.joblib"):
    """
    data_path: CSV with columns:
      semantic_similarity, skill_overlap, experience_match, label
      (label = 1 if candidate was shortlisted historically, else 0)
    """
    df = pd.read_csv(data_path)

    X = df[FEATURE_COLUMNS]
    y = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = GradientBoostingClassifier(
        n_estimators=100, max_depth=3, learning_rate=0.1, random_state=42
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    print(classification_report(y_test, preds))

    joblib.dump(model, model_out_path)
    print(f"Model saved to {model_out_path}")
    return model


def predict_score(model, features: dict) -> float:
    """Returns probability of being a strong-fit candidate (0-1)."""
    row = [[features[col] for col in FEATURE_COLUMNS]]
    prob = model.predict_proba(row)[0][1]
    return round(float(prob), 4)


if __name__ == "__main__":
    # Example: generate a small synthetic dataset to test the pipeline
    # before you have real labeled data.
    import numpy as np

    np.random.seed(42)
    n = 200
    synthetic = pd.DataFrame({
        "semantic_similarity": np.random.uniform(0.2, 0.95, n),
        "skill_overlap": np.random.uniform(0.0, 1.0, n),
        "experience_match": np.random.uniform(0.0, 1.0, n),
    })
    # Bootstrap rule-based label for synthetic training
    synthetic["label"] = (
        (synthetic["semantic_similarity"] > 0.55)
        & (synthetic["skill_overlap"] > 0.4)
    ).astype(int)

    synthetic.to_csv("synthetic_training_data.csv", index=False)
    train("synthetic_training_data.csv")
