"""
Feature engineering, used identically for training and live scoring.

Every feature for a transaction is computed from that transaction and the
customer's EARLIER transactions only. Nothing looks into the future, so the model
can't "cheat" during training, and live scoring (which only has the past)
produces the same numbers training did.
"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from .config import (
    CHANNELS,
    LOCAL_TIMEZONE,
    PAD_VALUE,
    RAW_COLUMNS,
    SEQUENCE_CONTINUOUS,
    SEQUENCE_FEATURES,
    SEQUENCE_LENGTH,
    TRANSACTION_TYPES,
)

_EPOCH = pd.Timestamp("1970-01-01", tz="UTC")
_DEFAULT_GAP_SECONDS = 7 * 24 * 3600  # "time since last transaction" for a customer's first one


def prepare_raw(raw: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalise a raw transaction frame (types, blanks, case)."""
    missing = [c for c in RAW_COLUMNS if c not in raw.columns]
    if missing:
        raise ValueError(f"Transaction data is missing columns: {missing}")

    df = raw.copy()
    df["user_id"] = df["user_id"].astype(str)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["amount"] = df["amount"].astype(float)
    for column in ("device_id", "country", "counterparty_account"):
        df[column] = df[column].fillna("").astype(str)  # blanks count as one "unknown" value
    for column in ("transaction_type", "channel"):
        df[column] = df[column].astype(str).str.lower()
    return df


def _window_stats(codes, seconds, amounts, window_seconds):
    """
    For each transaction: how many of the same customer's transactions (itself
    included) fall in the last `window_seconds`, and their total amount.

    Rows must be sorted by customer, then time, so each customer is one block.
    """
    n = len(seconds)
    counts = np.empty(n)
    sums = np.empty(n)
    edges = np.flatnonzero(np.diff(codes)) + 1  # where one customer's block ends
    for start, end in zip(np.r_[0, edges], np.r_[edges, n]):
        t = seconds[start:end]
        # First row of this customer that is still inside the window.
        first_in_window = np.searchsorted(t, t - window_seconds, side="left")
        position = np.arange(end - start)
        running_total = np.r_[0.0, np.cumsum(amounts[start:end])]
        counts[start:end] = position - first_in_window + 1
        sums[start:end] = running_total[position + 1] - running_total[first_in_window]
    return counts, sums


def build_features(raw: pd.DataFrame) -> pd.DataFrame:
    """
    Turn raw transactions into model features.

    Returns the frame sorted by (user_id, timestamp) with a fresh 0..n-1 index,
    so row i is always "the i-th transaction in that order" (the LSTM windows
    rely on this). Extra columns such as the fraud label are kept.
    """
    df = (
        prepare_raw(raw)
        .sort_values(["user_id", "timestamp"], kind="stable")
        .reset_index(drop=True)
    )

    by_user = df.groupby("user_id", sort=False)
    seconds = (df["timestamp"] - _EPOCH).dt.total_seconds().to_numpy()
    amount = df["amount"].to_numpy()
    codes = pd.factorize(df["user_id"])[0]            # a number per customer
    prior_count = by_user.cumcount().to_numpy()       # earlier transactions by this customer

    # --- Amount --------------------------------------------------------------
    df["log_amount"] = np.log1p(amount)

    # --- Time of day / week, in the customer's local time ----------------------
    local = df["timestamp"].dt.tz_convert(LOCAL_TIMEZONE)
    hour = local.dt.hour + local.dt.minute / 60.0
    df["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    df["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    df["is_night"] = (local.dt.hour < 6).astype(float)
    df["is_weekend"] = (local.dt.dayofweek >= 5).astype(float)

    # --- Pace: time since the previous transaction, and recent velocity ---------
    gap = pd.Series(seconds).groupby(df["user_id"], sort=False).diff()
    df["log_gap_seconds"] = np.log1p(gap.fillna(_DEFAULT_GAP_SECONDS).clip(lower=0)).to_numpy()

    # The `_` discards the amount sum, which is only wanted for the 24-hour window.
    df["txn_count_1h"], _ = _window_stats(codes, seconds, amount, 3600)
    df["txn_count_24h"], df["amount_sum_24h"] = _window_stats(codes, seconds, amount, 86400)

    # --- How unusual is this amount for THIS customer? --------------------------
    # Mean and variance of the customer's EARLIER log-amounts (this one excluded):
    # running total minus the current value.
    x = df["log_amount"]
    earlier_sum = x.groupby(df["user_id"], sort=False).cumsum().to_numpy() - x.to_numpy()
    earlier_sq = (x**2).groupby(df["user_id"], sort=False).cumsum().to_numpy() - (x**2).to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):  # a first transaction divides by 0
        mean = earlier_sum / prior_count
        variance = earlier_sq / prior_count - mean**2
    std = np.sqrt(np.clip(variance, 0.25, None))  # floor stops tiny variance exploding the score
    zscore = np.where(prior_count >= 3, (x.to_numpy() - mean) / std, 0.0)  # need a few points first
    df["amount_zscore"] = np.clip(np.nan_to_num(zscore), -10, 10)

    # --- Novelty: first time this customer uses this device / country / payee ----
    # The very first transaction has nothing to compare with, so it is never "new".
    has_history = prior_count > 0
    for flag, column in (
        ("new_device", "device_id"),
        ("new_country", "country"),
        ("new_counterparty", "counterparty_account"),
    ):
        first_use = ~df.duplicated(["user_id", column])
        df[flag] = (first_use.to_numpy() & has_history).astype(float)

    # --- One-hot columns --------------------------------------------------------
    for t in TRANSACTION_TYPES:
        df[f"type_{t}"] = (df["transaction_type"] == t).astype(float)
    for c in CHANNELS:
        df[f"channel_{c}"] = (df["channel"] == c).astype(float)

    return df


def fit_sequence_scaler(train_features: pd.DataFrame) -> StandardScaler:
    """Learn mean/std of the continuous LSTM inputs. Fit on TRAINING rows only."""
    return StandardScaler().fit(train_features[SEQUENCE_CONTINUOUS].to_numpy(dtype=float))


def build_sequences(df: pd.DataFrame, scaler: StandardScaler) -> np.ndarray:
    """
    For every transaction, the customer's last SEQUENCE_LENGTH transactions
    (itself last), shape (n_rows, SEQUENCE_LENGTH, n_features).

    Customers with fewer transactions are padded at the front with PAD_VALUE,
    which the LSTM's Masking layer ignores. `df` must come from build_features.
    """
    values = df[SEQUENCE_FEATURES].to_numpy(dtype=np.float32, copy=True)
    n_continuous = len(SEQUENCE_CONTINUOUS)  # these come first, and are standardised
    values[:, :n_continuous] = scaler.transform(df[SEQUENCE_CONTINUOUS].to_numpy(dtype=float))

    n_rows, n_features = values.shape
    window = np.full((n_rows, SEQUENCE_LENGTH, n_features), PAD_VALUE, dtype=np.float32)
    position = df.groupby("user_id", sort=False).cumcount().to_numpy()  # 0 = customer's first
    for lag in range(SEQUENCE_LENGTH):
        # Rows that have a transaction `lag` steps back from the same customer.
        rows = np.flatnonzero(position >= lag)
        window[rows, SEQUENCE_LENGTH - 1 - lag, :] = values[rows - lag]
    return window
