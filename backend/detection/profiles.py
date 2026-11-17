"""
A customer's "profile": what is normal for them, worked out from their own transactions.

The dashboard's payment form uses it (their usual device and country, the accounts they have
paid before) and so does the "what will be flagged" guide (their usual range for each kind of
payment, and the amounts where Medium, High and Critical begin).
"""

from collections import Counter

from fraud_engine.rules import amount_bands, purpose_name, purpose_of
from transactions.models import Transaction

from .demo_data import PAYEE_NAMES
from .services import is_trusted

# The kinds of payment the form offers, in the order shown.
PURPOSE_ORDER = ["airtime", "data", "electricity", "transfer", "withdrawal"]


def _most_common(values, default=""):
    values = [v for v in values if v]
    return Counter(values).most_common(1)[0][0] if values else default


def customer_profile(user, recent: int = 8) -> dict:
    # Only trusted payments count as "normal" (the same rule the history check uses).
    everything = Transaction.objects.select_related("detection_result").filter(user=user).order_by("-timestamp")
    transactions = [t for t in everything if is_trusted(t)]
    rows = [
        {
            "purpose": purpose_of({"merchant_category": t.merchant_category, "transaction_type": t.transaction_type}),
            "amount": float(t.amount),
            "when": t.timestamp,
            "payee": t.counterparty_account,
        }
        for t in transactions
    ]

    purposes = []
    for key in PURPOSE_ORDER:
        amounts = [r["amount"] for r in rows if r["purpose"] == key]
        entry = {"key": key, "label": purpose_name(key).capitalize(), "count": len(amounts)}
        if amounts:
            largest = max(amounts)
            bands = amount_bands(largest)
            entry.update(
                smallest=min(amounts),
                largest=largest,
                low_up_to=bands["low_up_to"],
                medium_up_to=bands["medium_up_to"],
                critical_from=bands["critical_from"],
            )
        purposes.append(entry)

    payees = sorted({r["payee"] for r in rows if r["purpose"] == "transfer" and r["payee"]})
    return {
        "id": str(user.pk),
        "email": user.email,
        "name": user.full_name or user.email,
        "usual_device": _most_common(t.device_id for t in transactions),
        "usual_country": _most_common((t.country for t in transactions), "NG"),
        "usual_city": _most_common(t.city for t in transactions),
        "transactions": len(rows),
        "purposes": purposes,
        "payees": [{"account": a, "name": PAYEE_NAMES.get(a, "")} for a in payees],
        "recent": [
            {"when": r["when"], "purpose": purpose_name(r["purpose"]), "amount": r["amount"], "payee": r["payee"]}
            for r in rows[:recent]
        ],
    }
