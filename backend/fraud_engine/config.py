"""
Constants shared by training and live scoring.

Both sides import the same lists, so they can never disagree about feature
names, feature order, window length or categories (a classic cause of models
that look great in training and fail in production).
"""

from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = BACKEND_DIR / "ml_artifacts"  # trained models are saved here
SEED = 42  # fixed seed so training runs are reproducible

# The raw columns every transaction must have. They mirror the Django
# Transaction model (with `user_id` standing for the customer), so rows exported
# from the database can be used for training without renaming anything.
RAW_COLUMNS = [
    "user_id",
    "timestamp",
    "amount",
    "transaction_type",
    "channel",
    "device_id",
    "country",
    "counterparty_account",
]
LABEL_COLUMN = "is_fraud"  # 1 = fraud, 0 = legitimate (training data only)

# Must match Transaction.TransactionType and Transaction.Channel in Django.
TRANSACTION_TYPES = ["transfer", "payment", "withdrawal", "deposit"]
CHANNELS = ["mobile_app", "web", "ussd", "pos", "atm", "card_not_present"]

# "Night" and "weekend" are judged in the customer's local time.
LOCAL_TIMEZONE = "Africa/Lagos"

# The LSTM looks at a customer's last 10 transactions (the current one included).
SEQUENCE_LENGTH = 10
# Fills the empty slots of a short history. Far outside any scaled value, and
# skipped by the LSTM's Masking layer.
PAD_VALUE = -999.0

# One-hot columns, one per transaction type and channel.
TYPE_FEATURES = [f"type_{t}" for t in TRANSACTION_TYPES]
CHANNEL_FEATURES = [f"channel_{c}" for c in CHANNELS]

# What XGBoost sees for one transaction (fixed order).
TABULAR_FEATURES = (
    [
        "amount",            # raw amount
        "log_amount",        # log(1 + amount), tames huge values
        "hour_sin",          # time of day on a circle, so 23:59 and 00:01 are close
        "hour_cos",
        "is_night",          # 00:00 to 05:59 local time
        "is_weekend",
        "log_gap_seconds",   # log(1 + seconds since the customer's previous transaction)
        "txn_count_1h",      # the customer's transactions in the last hour (this one included)
        "txn_count_24h",     # ...and in the last 24 hours
        "amount_sum_24h",    # total amount in the last 24 hours (this one included)
        "amount_zscore",     # how unusual this amount is for THIS customer
        "new_device",        # first time this customer uses this device
        "new_country",       # first time this customer transacts from this country
        "new_counterparty",  # first time this customer pays this account
    ]
    + TYPE_FEATURES
    + CHANNEL_FEATURES
)

# What the LSTM sees at each step of its window. The first block is standardised
# (mean 0, std 1) using statistics learned on the training data only.
SEQUENCE_CONTINUOUS = ["log_amount", "log_gap_seconds", "amount_zscore"]
SEQUENCE_FEATURES = (
    SEQUENCE_CONTINUOUS
    + ["hour_sin", "hour_cos", "new_device", "new_country", "new_counterparty"]
    + TYPE_FEATURES
    + CHANNEL_FEATURES
)

# Chronological split: oldest 60% trains the models, the next 10% stops training
# early (validation), the next 10% teaches the hybrid how to combine the two
# models, and the newest 20% is the final exam nobody has seen.
SPLIT_FRACTIONS = {"train": 0.6, "val": 0.1, "stack": 0.1}
