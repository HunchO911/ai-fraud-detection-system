"""
Training data.

`make_synthetic_data` builds a realistic fake bank so the whole pipeline works
today. `load_csv` loads your own data in the same shape (for example transactions
exported from Django, with analyst-confirmed labels).

Public datasets such as PaySim or the Kaggle credit-card set are a poor fit for a
sequence model: PaySim has almost one transaction per customer, and the Kaggle
set has no customer id at all, so there is no history for the LSTM to learn from.
"""

import numpy as np
import pandas as pd

from .config import CHANNELS, LABEL_COLUMN, RAW_COLUMNS, SEED, TRANSACTION_TYPES
from .features import prepare_raw

# How likely a customer is to transact at each LOCAL hour (0-23): quiet at night,
# busy through the working day.
_HOUR_WEIGHTS = np.array(
    [1, 1, 1, 1, 1, 2, 3, 5, 7, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 7, 6, 4, 3, 2], dtype=float
)
_HOUR_P = _HOUR_WEIGHTS / _HOUR_WEIGHTS.sum()
_FOREIGN = ["GB", "US", "GH", "KE", "ZA", "CN", "RU"]  # countries a customer might appear in abroad


def load_csv(path) -> pd.DataFrame:
    """Load a CSV with the RAW_COLUMNS plus an `is_fraud` column (0/1)."""
    df = pd.read_csv(
        path,
        dtype={"user_id": str, "device_id": str, "country": str, "counterparty_account": str},
    )
    if LABEL_COLUMN not in df.columns:
        raise ValueError(f"The CSV needs a '{LABEL_COLUMN}' column with 0/1 labels.")
    df = prepare_raw(df)  # also checks that every raw column is present
    df[LABEL_COLUMN] = df[LABEL_COLUMN].astype(int)
    return df[RAW_COLUMNS + [LABEL_COLUMN]]


# ---------------------------------------------------------------------------
# Synthetic bank. Each helper returns one block of transactions for one customer.
# `start` is the epoch second of day 0 (midnight UTC). Lagos is UTC+1, so
# "local hour h" is `h * 3600 - 3600` seconds after midnight UTC.
# ---------------------------------------------------------------------------
def _frame(user_id, seconds, amounts, types, channels, devices, countries, payees, label):
    """Assemble one block of transactions into a DataFrame."""
    return pd.DataFrame(
        {
            "user_id": user_id,
            "timestamp": pd.to_datetime(np.asarray(seconds, dtype=float), unit="s", utc=True),
            "amount": np.maximum(np.round(np.asarray(amounts, dtype=float), 2), 1.0),
            "transaction_type": list(types),
            "channel": list(channels),
            "device_id": list(devices),
            "country": list(countries),
            "counterparty_account": list(payees),
            LABEL_COLUMN: label,
        }
    )


def _legit(rng, profile, days, start):
    """A customer's everyday activity: familiar device, country and payees, usual amounts."""
    uid = profile["user_id"]
    n = max(int(rng.poisson(profile["rate"] * days)), 3)  # at least 3 transactions each

    seconds = (
        start
        + rng.integers(0, days, n) * 86400                 # which day
        + rng.choice(24, n, p=_HOUR_P) * 3600              # which local hour
        - 3600                                             # local time -> UTC
        + rng.integers(0, 3600, n)                         # which second within the hour
    )
    devices = np.array(profile["devices"], dtype=object)[rng.integers(0, len(profile["devices"]), n)]
    payees = np.array(profile["payees"], dtype=object)[rng.integers(0, len(profile["payees"]), n)]

    # Honest novelty: now and then a customer uses a new phone, or pays someone new.
    # Without this, "new device" would give fraud away trivially.
    new_device = rng.random(n) < 0.02
    devices[new_device] = [f"{uid}_alt{i}" for i in np.flatnonzero(new_device)]
    new_payee = rng.random(n) < 0.1
    payees[new_payee] = [f"{uid}_payee_new{i}" for i in np.flatnonzero(new_payee)]
    countries = np.where(rng.random(n) < 0.015, rng.choice(_FOREIGN, n), "NG")  # rare foreign use

    return _frame(
        uid,
        seconds,
        rng.lognormal(profile["mu"], 0.7, n),
        rng.choice(TRANSACTION_TYPES, n, p=[0.35, 0.4, 0.15, 0.1]),
        rng.choice(CHANNELS, n, p=profile["channel_p"]),
        devices,
        countries,
        payees,
        0,
    )


def _spree(rng, profile, days, start):
    """HARD NEGATIVE: an honest shopping spree (several quick payments, all legitimate)."""
    uid = profile["user_id"]
    k = int(rng.integers(3, 6))
    t0 = start + rng.integers(0, days) * 86400 + rng.integers(9, 20) * 3600 - 3600
    return _frame(
        uid,
        t0 + np.cumsum(rng.exponential(420, k)),           # a purchase every ~7 minutes
        rng.lognormal(profile["mu"] + 0.3, 0.4, k),
        ["payment"] * k,
        rng.choice(["pos", "web"], k),
        [profile["devices"][0]] * k,
        ["NG"] * k,
        [f"{uid}_shop{j}" for j in range(k)],
        0,
    )


def _travel(rng, profile, days, start):
    """HARD NEGATIVE: an honest trip abroad (new country AND a new phone, normal amounts)."""
    uid = profile["user_id"]
    k = int(rng.integers(4, 9))
    t0 = start + rng.integers(0, max(days - 2, 1)) * 86400 + 28800
    return _frame(
        uid,
        t0 + np.sort(rng.uniform(0, 172800, k)),           # spread over two days
        rng.lognormal(profile["mu"], 0.7, k),
        rng.choice(["payment", "withdrawal"], k),
        rng.choice(["mobile_app", "pos"], k),
        [f"{uid}_travel"] * k,
        [str(rng.choice(_FOREIGN))] * k,
        rng.choice(profile["payees"], k),
        0,
    )


def _fraud_episode(rng, profile, days, start, index):
    """
    Fraud: either an account takeover (a burst of large transfers from a new
    device, usually at night, often from abroad) or a single large online card payment.
    """
    uid = profile["user_id"]
    night = rng.random() < 0.6
    local_hour = int(rng.choice([22, 23, 0, 1, 2, 3, 4, 5])) if night else int(rng.integers(6, 22))
    t0 = start + rng.integers(0, days) * 86400 + local_hour * 3600 - 3600 + rng.integers(0, 3600)
    country = str(rng.choice(_FOREIGN)) if rng.random() < 0.7 else "NG"
    device = f"{uid}_fraud{index}"  # the attacker's device, never seen before

    if rng.random() < 0.7:  # account takeover: several large transfers to a "mule" account
        k = int(rng.integers(3, 9))
        return _frame(
            uid,
            t0 + np.cumsum(rng.exponential(480, k)),       # one every ~8 minutes
            np.exp(profile["mu"] + rng.normal(1.0, 0.5, k)),  # roughly 2.7x the usual amount
            rng.choice(["transfer", "withdrawal", "payment"], k, p=[0.5, 0.3, 0.2]),
            rng.choice(["mobile_app", "web", "ussd"], k),
            [device] * k,
            [country] * k,
            [f"mule_{uid}_{index}"] * k,
            1,
        )

    # A single big card-not-present payment to a fraudulent merchant.
    return _frame(
        uid,
        [t0],
        np.exp(profile["mu"] + rng.normal(1.5, 0.4, 1)),   # roughly 4.5x the usual amount
        ["payment"],
        ["card_not_present"],
        [device],
        [country],
        [f"{uid}_merchant_fraud{index}"],
        1,
    )


def make_synthetic_data(n_users: int = 1500, days: int = 60, seed: int = SEED) -> pd.DataFrame:
    """
    Simulate `n_users` customers over `days` days. Roughly 1% of transactions are
    fraud, mixed in with honest-but-unusual activity (shopping sprees, foreign
    travel, a new phone) so the task isn't trivially easy.
    """
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2026-01-01", tz="UTC").timestamp()
    frames = []

    for u in range(n_users):
        uid = f"user_{u:05d}"
        profile = {
            "user_id": uid,
            "mu": rng.normal(9.0, 0.6),                  # usual log-amount (median about 8,100 NGN)
            "rate": rng.lognormal(0.1, 0.5),             # transactions per day
            "devices": [f"{uid}_dev{i}" for i in range(int(rng.integers(1, 3)))],
            "payees": [f"{uid}_payee{j}" for j in range(int(rng.integers(4, 12)))],
            "channel_p": rng.dirichlet(np.full(len(CHANNELS), 0.6)),  # favourite channels
        }
        frames.append(_legit(rng, profile, days, start))
        if rng.random() < 0.04:                          # 4% of customers go on a shopping spree
            frames.append(_spree(rng, profile, days, start))
        if rng.random() < 0.02:                          # 2% travel abroad
            frames.append(_travel(rng, profile, days, start))
        if rng.random() < 0.12:                          # 12% suffer 1-3 fraud episodes
            for episode in range(int(rng.integers(1, 4))):
                frames.append(_fraud_episode(rng, profile, days, start, episode))

    df = pd.concat(frames, ignore_index=True)
    df = df.sort_values("timestamp", kind="stable").reset_index(drop=True)
    return df[RAW_COLUMNS + [LABEL_COLUMN]]
