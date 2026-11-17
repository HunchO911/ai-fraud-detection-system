"""
The history check: judge a new transaction by comparing it with the customer's own past.

No training and no data files. The question it answers is the one a bank clerk asks:
"Is this normal for THIS customer?"

For a new transaction we look at the customer's earlier transactions and add up points
(a probability from 0 to 1, shown as a percentage on the dashboard):

    How big is it?        Compare the amount with the LARGEST earlier payment of the same
                          kind (airtime, data, bills, transfers...). Never paid this kind
                          before? Compare with their largest payment of any kind.

                              up to the largest            +0      (normal for them)
                              above it, up to 3 x          +0.35
                              3 to 10 x                    +0.65
                              10 x or more                 +0.85

    Something new?        first time paying for this kind of thing   +0.30
                          first time on this device                  +0.30
                          first time from this country               +0.30
                          first time paying this account             +0.15   (transfers)
                          late at night (00:00-05:59) and never before +0.10
    Too fast?             4+ transactions in the last hour           +0.30
                          6+ transactions in the last hour           +0.60
    Too little history?   fewer than 3 earlier transactions          +0.30

Because anything above their usual maximum is at least Medium, and only Low or analyst-cleared
payments count as "normal", nobody can creep upward in small steps.

The points are added (maximum 99%). With the default risk levels on the Settings page
(medium 30%, high 60%, critical 85%) that means:

    Low      the amount is within what they have paid before, and nothing else is odd
    Medium   one thing is odd (a new device, or more than they have ever paid, up to 3 x)
    High     the amount is far above anything they have paid, or two odd things at once
    Critical 10 x their usual amount, or several odd things together

Everything here is plain Python so it is easy to read, test and explain. The same
numbers are reused by `amount_bands()` so the dashboard can tell you in advance which
amounts will be flagged for each customer.
"""

from datetime import timedelta, timezone

MODEL_VERSION = "history-rules-1"

# Lagos is UTC+1 all year (no daylight saving), so a fixed offset is exact.
LOCAL = timezone(timedelta(hours=1))

# --- the points (see the table above) ---
# (ratio at most, points). Above the last row: 0.65 below 10 x, 0.85 from 10 x.
AMOUNT_TIERS = [(1.0, 0.0), (3.0, 0.35)]
HIGH_POINTS = 0.65
CRITICAL_POINTS = 0.85
CRITICAL_RATIO = 10.0
POINTS = {
    "first_of_kind": 0.30,
    "new_device": 0.30,
    "new_country": 0.30,
    "new_payee": 0.15,
    "night": 0.10,
    "fast_4": 0.30,
    "fast_6": 0.60,
    "thin_history": 0.30,
}
THIN_HISTORY = 3  # fewer earlier transactions than this counts as "not enough history"

PURPOSE_NAMES = {
    "airtime": "airtime",
    "data": "data bundle",
    "electricity": "electricity bill",
    "transfer": "transfer",
    "withdrawal": "cash withdrawal",
    "payment": "payment",
    "deposit": "deposit",
}


def purpose_of(row: dict) -> str:
    """What the money is for: the merchant category (airtime, data...) or else the type (transfer...)."""
    return (row.get("merchant_category") or "").strip().lower() or (row.get("transaction_type") or "payment")


def purpose_name(purpose: str) -> str:
    return PURPOSE_NAMES.get(purpose, purpose.replace("_", " "))


def _naira(value: float) -> str:
    return f"₦{value:,.0f}"


def amount_points(ratio: float) -> float:
    """Points for an amount that is `ratio` times the customer's largest comparable payment."""
    if ratio >= CRITICAL_RATIO:
        return CRITICAL_POINTS
    for limit, points in AMOUNT_TIERS:
        if ratio <= limit:
            return points
    return HIGH_POINTS


def amount_bands(largest: float) -> dict:
    """
    The amounts that land in each band, for a customer whose largest comparable payment is
    `largest`. Used by the dashboard's "what will be flagged" guide. Percentages assume
    nothing else is odd (usual device, usual country, no rush).
    """
    return {
        "low_up_to": largest,             # up to this: low
        "medium_up_to": largest * 3.0,    # above the last, up to this: medium
        "critical_from": largest * CRITICAL_RATIO,  # above medium_up_to and below this: high; this or more: critical
    }


def _as_datetime(value):
    # pandas Timestamps and datetimes both work; make sure we have timezone-aware values.
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    return value


def assess(history: list[dict]) -> dict:
    """
    Judge the LAST transaction in `history` (oldest first) against the ones before it.

    Each row is a dict with: timestamp, amount, transaction_type, merchant_category,
    channel, device_id, country, counterparty_account, and optionally `trusted` (False for
    payments that were flagged: they are ignored when working out what is normal).

    Returns {"probability": 0-1, "reasons": {sentence: points}} where points above 0 raised
    the risk and points below 0 lowered it (shown in green on the alert page).
    """
    *earlier_all, current = history
    # What counts as "normal for them" is learned only from payments that were trusted: low risk,
    # or cleared by an analyst. A payment that was flagged does not become the new normal.
    # (Speed is different: every recent payment counts, trusted or not.)
    earlier = [r for r in earlier_all if r.get("trusted", True)]
    reasons: dict[str, float] = {}
    total = 0.0

    def raise_risk(sentence: str, points: float) -> None:
        nonlocal total
        total += points
        reasons[sentence] = round(points, 2)

    purpose = purpose_of(current)
    kind = purpose_name(purpose)
    amount = float(current["amount"])

    same_kind = [float(r["amount"]) for r in earlier if purpose_of(r) == purpose]
    any_kind = [float(r["amount"]) for r in earlier]

    # --- 1. Not enough history to judge ---
    if len(earlier) < THIN_HISTORY:
        raise_risk(
            f"Only {len(earlier)} earlier transaction{'s' if len(earlier) != 1 else ''} to compare with",
            POINTS["thin_history"],
        )

    # --- 2. How big is the amount compared with what they have paid before? ---
    if same_kind:
        largest = max(same_kind)
        scope = f"{kind}"
    elif any_kind:
        largest = max(any_kind)
        scope = "payment of any kind"
        raise_risk(f"First time paying for {kind}", POINTS["first_of_kind"])
    else:
        largest = 0.0
        scope = ""

    if largest > 0:
        ratio = amount / largest
        points = amount_points(ratio)
        if points > 0:
            if ratio >= 10:
                size = f"{ratio:.0f} times"
            elif ratio >= 2:
                size = f"{ratio:.1f} times"
            else:
                size = f"{(ratio - 1) * 100:.0f}% above"
            raise_risk(f"{_naira(amount)} {kind} is {size} their largest {scope} ({_naira(largest)})", points)
        else:
            low, high = min(same_kind or any_kind), largest
            reasons[f"{_naira(amount)} {kind} is within their usual {scope} range ({_naira(low)} to {_naira(high)})"] = -0.2

    # --- 3. Anything new? ---
    devices = {r.get("device_id") for r in earlier if r.get("device_id")}
    if current.get("device_id") and devices and current["device_id"] not in devices:
        raise_risk("First time on this device", POINTS["new_device"])
    elif current.get("device_id") and devices:
        reasons["Usual device"] = -0.1

    countries = {r.get("country") for r in earlier if r.get("country")}
    if current.get("country") and countries and current["country"] not in countries:
        raise_risk(f"First time from {current['country']}", POINTS["new_country"])

    if purpose == "transfer" and current.get("counterparty_account"):
        payees = {r.get("counterparty_account") for r in earlier if r.get("counterparty_account")}
        if current["counterparty_account"] not in payees:
            raise_risk("First time paying this account", POINTS["new_payee"])
        else:
            reasons["Account they have paid before"] = -0.1

    # --- 4. Time of day ---
    now = _as_datetime(current["timestamp"])
    if 0 <= now.astimezone(LOCAL).hour < 6:
        usual_night = any(0 <= _as_datetime(r["timestamp"]).astimezone(LOCAL).hour < 6 for r in earlier)
        if not usual_night:
            raise_risk("Made late at night, which they never do", POINTS["night"])

    # --- 5. Too many, too fast ---
    hour_ago = now - timedelta(hours=1)
    recent = 1 + sum(1 for r in earlier_all if _as_datetime(r["timestamp"]) > hour_ago)
    if recent >= 6:
        raise_risk(f"{recent} transactions in the last hour", POINTS["fast_6"])
    elif recent >= 4:
        raise_risk(f"{recent} transactions in the last hour", POINTS["fast_4"])

    # Never exactly 0% or 100%: a clean payment still carries a little residual risk.
    return {"probability": min(0.99, max(0.02, round(total, 2))), "reasons": reasons}


class RulesPredictor:
    """Same `predict(history)` shape as the AI model's predictor, so the rest of the app is unchanged."""

    model_version = MODEL_VERSION

    def predict(self, history) -> dict:
        rows = history.to_dict("records") if hasattr(history, "to_dict") else list(history)
        verdict = assess(rows)
        p = verdict["probability"]
        return {
            "xgboost_score": p,  # (the field name is historical: this is the history-check score)
            "lstm_score": None,
            "fraud_probability": p,
            "model_version": MODEL_VERSION,
            "top_features": verdict["reasons"],
            "processing_time_ms": 1,
        }
