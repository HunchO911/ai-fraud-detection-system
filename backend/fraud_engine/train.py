"""
Train the hybrid fraud model and save everything Django needs.

    python -m fraud_engine.train                      # synthetic data (default)
    python -m fraud_engine.train --csv my_data.csv    # your own labelled transactions
    python -m fraud_engine.train --epochs 5 --users 500   # quick smoke run

Steps: build features -> chronological split -> train XGBoost -> train LSTM ->
fit the hybrid combiner -> evaluate on unseen newest data -> save -> check that
live scoring reproduces the training numbers.
"""

import argparse
import json
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, confusion_matrix, roc_auc_score

from .config import (
    ARTIFACTS_DIR,
    LABEL_COLUMN,
    LOCAL_TIMEZONE,
    PAD_VALUE,
    RAW_COLUMNS,
    SEED,
    SEQUENCE_FEATURES,
    SEQUENCE_LENGTH,
    SPLIT_FRACTIONS,
    TABULAR_FEATURES,
)
from .data import load_csv, make_synthetic_data
from .features import build_features, build_sequences, fit_sequence_scaler
from .hybrid import best_f1_threshold, combine, fit_meta_model, suggest_risk_thresholds


# ---------------------------------------------------------------------------
# Splitting and evaluation
# ---------------------------------------------------------------------------
def time_split_masks(timestamps: pd.Series) -> dict:
    """
    Split rows by time: oldest -> train, then val, then stack, newest -> test.
    A random split would let the model train on the future and be tested on the
    past, which flatters the results. Real fraud detection always predicts forward.
    """
    position = timestamps.rank(method="first", pct=True).to_numpy()  # 0..1 by time
    train_end = SPLIT_FRACTIONS["train"]
    val_end = train_end + SPLIT_FRACTIONS["val"]
    stack_end = val_end + SPLIT_FRACTIONS["stack"]
    return {
        "train": position <= train_end,
        "val": (position > train_end) & (position <= val_end),
        "stack": (position > val_end) & (position <= stack_end),
        "test": position > stack_end,
    }


def evaluate(name: str, y_true, scores, threshold: float) -> dict:
    """Ranking quality (PR-AUC, ROC-AUC) and the confusion matrix at one threshold."""
    predicted = scores >= threshold
    tn, fp, fn, tp = confusion_matrix(y_true, predicted, labels=[0, 1]).ravel()
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    return {
        "model": name,
        "pr_auc": float(average_precision_score(y_true, scores)),
        "roc_auc": float(roc_auc_score(y_true, scores)),
        "threshold": float(threshold),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(2 * precision * recall / max(precision + recall, 1e-12)),
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
    }


def print_results(rows: list) -> None:
    print(f"\n{'model':<10}{'PR-AUC':>9}{'ROC-AUC':>9}{'thresh':>9}{'precision':>11}{'recall':>9}{'F1':>8}")
    for r in rows:
        print(f"{r['model']:<10}{r['pr_auc']:>9.3f}{r['roc_auc']:>9.3f}{r['threshold']:>9.3f}"
              f"{r['precision']:>11.3f}{r['recall']:>9.3f}{r['f1']:>8.3f}")
    hybrid = rows[-1]
    print(f"\nHybrid confusion matrix on the test set: "
          f"caught {hybrid['tp']} fraud, missed {hybrid['fn']}, "
          f"false alarms {hybrid['fp']}, correctly passed {hybrid['tn']}")


# ---------------------------------------------------------------------------
# Model 1: XGBoost (looks at one transaction's features)
# ---------------------------------------------------------------------------
def train_xgboost(X_train, y_train, X_val, y_val):
    from xgboost import XGBClassifier  # imported here so the rest works without it

    positives = int(y_train.sum())
    negatives = len(y_train) - positives
    model = XGBClassifier(
        n_estimators=800,            # upper limit; early stopping picks the real number
        learning_rate=0.05,
        max_depth=6,
        min_child_weight=3,
        subsample=0.8,
        colsample_bytree=0.8,
        # Fraud is rare, so tell XGBoost each fraud example counts for many normal ones.
        scale_pos_weight=negatives / max(positives, 1),
        eval_metric="aucpr",
        early_stopping_rounds=40,    # stop when the validation score stops improving
        tree_method="hist",
        n_jobs=-1,
        random_state=SEED,
    )
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    return model


def xgb_scores(model, X) -> np.ndarray:
    """Fraud probability from XGBoost, always using the best (early-stopped) trees."""
    return model.predict_proba(X, iteration_range=(0, model.best_iteration + 1))[:, 1]


# ---------------------------------------------------------------------------
# Model 2: LSTM (looks at the customer's last 10 transactions in order)
# ---------------------------------------------------------------------------
def build_lstm(n_features: int):
    from tensorflow import keras
    from tensorflow.keras import layers

    inputs = keras.Input(shape=(SEQUENCE_LENGTH, n_features))
    x = layers.Masking(mask_value=PAD_VALUE)(inputs)   # skip the padded empty slots
    x = layers.LSTM(64)(x)                             # summarises the sequence
    x = layers.Dropout(0.3)(x)                         # reduces overfitting
    x = layers.Dense(32, activation="relu")(x)
    outputs = layers.Dense(1, activation="sigmoid")(x)  # fraud probability
    model = keras.Model(inputs, outputs)
    model.compile(
        optimizer=keras.optimizers.Adam(1e-3),
        loss="binary_crossentropy",
        metrics=[keras.metrics.AUC(name="pr_auc", curve="PR")],
    )
    return model


def train_lstm(X_train, y_train, X_val, y_val, epochs: int):
    from tensorflow import keras

    keras.utils.set_random_seed(SEED)
    positives = float(y_train.sum())
    negatives = len(y_train) - positives
    # Softer than the full imbalance ratio: a huge weight makes LSTM training unstable.
    fraud_weight = float(min(np.sqrt(negatives / max(positives, 1)), 20.0))

    model = build_lstm(X_train.shape[2])
    model.fit(
        X_train, y_train.astype("float32"),
        validation_data=(X_val, y_val.astype("float32")),
        epochs=epochs,
        batch_size=512,
        class_weight={0: 1.0, 1: fraud_weight},
        callbacks=[keras.callbacks.EarlyStopping(
            monitor="val_pr_auc", mode="max", patience=5, restore_best_weights=True
        )],
        verbose=2,
    )
    return model


def lstm_scores(model, X) -> np.ndarray:
    return model.predict(X, batch_size=2048, verbose=0).ravel()


# ---------------------------------------------------------------------------
# Saving and checking
# ---------------------------------------------------------------------------
def save_artifacts(out_dir, xgb_model, lstm_model, scaler, meta_model, metadata: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    xgb_model.save_model(str(out_dir / "xgboost_model.json"))
    lstm_model.save(out_dir / "lstm_model.keras")
    joblib.dump(scaler, out_dir / "sequence_scaler.joblib")
    joblib.dump(meta_model, out_dir / "meta_model.joblib")
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))


def check_serving_matches_training(df, masks, hybrid_test, out_dir, samples: int = 20) -> float:
    """
    Reload the saved models through the same FraudPredictor Django will use, and
    score real test transactions one at a time from raw history. The numbers must
    match what batch training produced; if not, training and serving have drifted.
    """
    from .predictor import FraudPredictor

    predictor = FraudPredictor(out_dir)
    test_rows = np.flatnonzero(masks["test"])
    labels = df[LABEL_COLUMN].to_numpy()[test_rows]
    # Prefer fraud rows (the interesting ones), then fill with normal rows.
    order = np.argsort(-labels, kind="stable")[:samples]

    worst = 0.0
    for k in order:
        row = test_rows[k]
        user = df.at[row, "user_id"]
        history = df.loc[(df["user_id"] == user) & (df.index <= row), RAW_COLUMNS]
        live = predictor.predict(history)["fraud_probability"]
        worst = max(worst, abs(live - float(hybrid_test[k])))
    return worst


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Train the hybrid fraud model.")
    parser.add_argument("--csv", help="CSV of labelled transactions (default: synthetic data)")
    parser.add_argument("--users", type=int, default=1500, help="synthetic customers")
    parser.add_argument("--days", type=int, default=60, help="synthetic days of history")
    parser.add_argument("--epochs", type=int, default=25, help="maximum LSTM epochs")
    parser.add_argument("--out", default=str(ARTIFACTS_DIR), help="where to save the models")
    args = parser.parse_args()

    # 1. Data
    raw = load_csv(args.csv) if args.csv else make_synthetic_data(args.users, args.days)
    source = args.csv or "synthetic"
    print(f"Data ({source}): {len(raw):,} transactions, {raw[LABEL_COLUMN].mean():.2%} fraud")

    # 2. Features and chronological split
    df = build_features(raw)
    y = df[LABEL_COLUMN].to_numpy(dtype=int)
    masks = time_split_masks(df["timestamp"])
    for name, mask in masks.items():
        print(f"  {name:<6}{mask.sum():>8,} rows, {y[mask].sum():>5,} fraud")
    if y[masks["stack"]].sum() < 30 or y[masks["test"]].sum() < 30:
        print("  WARNING: very few fraud cases in the stack/test sets; results will be noisy.")

    scaler = fit_sequence_scaler(df[masks["train"]])  # fitted on training rows only
    X_tab = df[TABULAR_FEATURES]
    X_seq = build_sequences(df, scaler)

    # 3. Base models
    print("\nTraining XGBoost...")
    xgb_model = train_xgboost(X_tab[masks["train"]], y[masks["train"]],
                              X_tab[masks["val"]], y[masks["val"]])
    print(f"  best iteration: {xgb_model.best_iteration}")
    top = sorted(zip(TABULAR_FEATURES, xgb_model.feature_importances_), key=lambda t: -t[1])[:6]
    print("  most important features:", ", ".join(f"{n} ({v:.2f})" for n, v in top))

    print("\nTraining LSTM...")
    lstm_model = train_lstm(X_seq[masks["train"]], y[masks["train"]],
                            X_seq[masks["val"]], y[masks["val"]], args.epochs)

    # 4. Hybrid: learn how to combine the two on data neither has seen
    xgb_stack = xgb_scores(xgb_model, X_tab[masks["stack"]])
    lstm_stack = lstm_scores(lstm_model, X_seq[masks["stack"]])
    meta_model = fit_meta_model(xgb_stack, lstm_stack, y[masks["stack"]])
    hybrid_stack = combine(meta_model, xgb_stack, lstm_stack)
    print(f"\nHybrid weights (logit scale): XGBoost {meta_model.coef_[0][0]:.2f}, "
          f"LSTM {meta_model.coef_[0][1]:.2f}, bias {meta_model.intercept_[0]:.2f}")

    # 5. Final exam on the newest, untouched data. Each model gets its own best
    #    threshold, chosen on the stack set (never on the test set).
    xgb_test = xgb_scores(xgb_model, X_tab[masks["test"]])
    lstm_test = lstm_scores(lstm_model, X_seq[masks["test"]])
    hybrid_test = combine(meta_model, xgb_test, lstm_test)
    y_test = y[masks["test"]]

    hybrid_threshold = best_f1_threshold(y[masks["stack"]], hybrid_stack)
    results = [
        evaluate("XGBoost", y_test, xgb_test, best_f1_threshold(y[masks["stack"]], xgb_stack)),
        evaluate("LSTM", y_test, lstm_test, best_f1_threshold(y[masks["stack"]], lstm_stack)),
        evaluate("Hybrid", y_test, hybrid_test, hybrid_threshold),
    ]
    print_results(results)

    # 6. Save
    import sklearn
    import tensorflow
    import xgboost

    out_dir = type(ARTIFACTS_DIR)(args.out)
    metadata = {
        "model_version": "hybrid-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "data_source": source,
        "n_transactions": int(len(df)),
        "fraud_rate": float(y.mean()),
        "tabular_features": TABULAR_FEATURES,
        "sequence_features": SEQUENCE_FEATURES,
        "sequence_length": SEQUENCE_LENGTH,
        "pad_value": PAD_VALUE,
        "local_timezone": LOCAL_TIMEZONE,
        "xgboost_best_iteration": int(xgb_model.best_iteration),
        "decision_threshold": hybrid_threshold,
        "suggested_risk_thresholds": suggest_risk_thresholds(
            y[masks["stack"]], hybrid_stack, hybrid_threshold
        ),
        "test_metrics": results,
        # Saved models only load reliably on matching library versions.
        "library_versions": {
            "scikit-learn": sklearn.__version__,
            "xgboost": xgboost.__version__,
            "tensorflow": tensorflow.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
    }
    save_artifacts(out_dir, xgb_model, lstm_model, scaler, meta_model, metadata)
    print(f"\nSaved to {out_dir} (version {metadata['model_version']})")
    print("Suggested settings.FRAUD_DETECTION['RISK_THRESHOLDS']:",
          metadata["suggested_risk_thresholds"])

    # 7. Prove the saved models score live transactions exactly like training did
    worst = check_serving_matches_training(df, masks, hybrid_test, out_dir)
    status = "OK" if worst < 1e-3 else "MISMATCH: investigate before using in production"
    print(f"Serving check: largest difference {worst:.2e} -> {status}")


if __name__ == "__main__":
    main()
