"""Tests for the history check, using the three hand-written demo customers."""

import unittest
from datetime import datetime, timedelta

from detection.demo_data import CUSTOMERS, PURPOSES
from fraud_engine.rules import LOCAL, RulesPredictor, amount_bands, assess

NOW = datetime(2026, 11, 17, 11, 0, tzinfo=LOCAL)  # a Tuesday morning


def history_rows(customer):
    rows = []
    for days, hour, purpose, amount, payee in customer["history"]:
        tx_type, category, _, channel = PURPOSES[purpose]
        rows.append({
            "timestamp": (NOW - timedelta(days=days)).replace(hour=hour),
            "amount": amount, "transaction_type": tx_type, "merchant_category": category,
            "channel": channel, "device_id": customer["device"], "country": "NG",
            "counterparty_account": payee,
        })
    return rows


def judge(name, purpose, amount, payee="", device=None, country="NG", when=NOW, extra=()):
    """Probability for a new payment by one customer (first name, lower case)."""
    customer = next(c for c in CUSTOMERS if c["first_name"].lower() == name)
    tx_type, category, _, channel = PURPOSES[purpose]
    new = {
        "timestamp": when, "amount": amount, "transaction_type": tx_type, "merchant_category": category,
        "channel": channel, "device_id": device or customer["device"], "country": country,
        "counterparty_account": payee,
    }
    return assess(history_rows(customer) + list(extra) + [new])


def level(p):  # the default risk levels from the Settings page
    return "critical" if p >= 0.85 else "high" if p >= 0.60 else "medium" if p >= 0.30 else "low"


class DemoCustomerTests(unittest.TestCase):
    def check(self, expected, *args, **kwargs):
        verdict = judge(*args, **kwargs)
        self.assertEqual(level(verdict["probability"]), expected, verdict)
        return verdict

    # ---- Chidi: airtime 500-2,000; data 3,500; electricity up to 18,000; transfers up to 30,000 ----
    def test_chidi_usual_airtime_is_low(self):
        self.check("low", "chidi", "airtime", 1500)
        self.check("low", "chidi", "airtime", 2000)
        self.check("medium", "chidi", "airtime", 2100)   # even slightly above his largest is Medium
        self.check("medium", "chidi", "airtime", 3000)

    def test_chidi_airtime_bands(self):
        self.check("medium", "chidi", "airtime", 5000)    # 2.5 x
        self.check("high", "chidi", "airtime", 10000)     # 5 x
        self.check("critical", "chidi", "airtime", 20000) # 10 x
        self.check("critical", "chidi", "airtime", 50000)

    def test_chidi_transfers(self):
        self.check("low", "chidi", "transfer", 30000, payee="0123456789")
        self.check("low", "chidi", "transfer", 30000, payee="0999999999")      # new account alone is only +15%
        self.check("high", "chidi", "transfer", 100000, payee="0999999999")    # 3.3 x and a new account
        self.check("critical", "chidi", "transfer", 300000, payee="0999999999")

    def test_chidi_data_and_bills(self):
        self.check("low", "chidi", "data", 3500)
        self.check("high", "chidi", "data", 20000)
        self.check("low", "chidi", "electricity", 16000)

    # ---- Ngozi: transfers up to 250,000; electricity up to 40,000; airtime up to 10,000 ----
    def test_ngozi(self):
        self.check("low", "ngozi", "transfer", 200000, payee="0234567890")
        self.check("medium", "ngozi", "transfer", 400000, payee="0234567890")   # 1.6 x
        self.check("high", "ngozi", "transfer", 1000000, payee="0999999999")    # 4 x + new account
        self.check("low", "ngozi", "airtime", 8000)
        self.check("high", "ngozi", "airtime", 50000)                            # 5 x

    # ---- Tunde: airtime 200-500; data up to 1,500; has never paid a bill ----
    def test_tunde(self):
        self.check("low", "tunde", "airtime", 500)
        self.check("medium", "tunde", "airtime", 750)    # 1.5 x
        self.check("medium", "tunde", "airtime", 1000)   # 2 x
        self.check("critical", "tunde", "airtime", 5000)
        self.check("critical", "tunde", "airtime", 50000)

    def test_first_time_bill_is_medium_but_a_big_one_is_critical(self):
        verdict = self.check("medium", "tunde", "electricity", 5000)   # first time + within his largest payment (10,000)
        self.assertIn("First time paying for electricity bill", verdict["reasons"])
        self.check("critical", "tunde", "electricity", 50000)

    # ---- other signals ----
    def test_new_device_and_country(self):
        self.check("medium", "chidi", "airtime", 1000, device="stranger-phone")
        self.check("medium", "chidi", "airtime", 1000, country="RU")
        self.check("high", "chidi", "airtime", 1000, device="stranger-phone", country="RU")
        self.check("critical", "chidi", "transfer", 850000, payee="0999999999", device="x", country="RU")

    def test_night_and_speed(self):
        night = NOW.replace(hour=3)
        self.check("low", "chidi", "airtime", 1000, when=night)  # 10% alone is still low
        rapid = [
            {"timestamp": NOW - timedelta(minutes=m), "amount": 500, "transaction_type": "payment",
             "merchant_category": "airtime", "channel": "mobile_app", "device_id": "chidi-iphone-13",
             "country": "NG", "counterparty_account": ""}
            for m in (50, 40, 30)
        ]
        self.check("medium", "chidi", "airtime", 500, extra=rapid)  # the 4th in an hour

    def test_untrusted_history_is_not_the_new_normal(self):
        # A 50,000 airtime payment that was flagged earlier must not make 50,000 look normal.
        flagged = {"timestamp": NOW - timedelta(days=1), "amount": 50000, "transaction_type": "payment",
                   "merchant_category": "airtime", "channel": "mobile_app", "device_id": "chidi-iphone-13",
                   "country": "NG", "counterparty_account": "", "trusted": False}
        self.check("critical", "chidi", "airtime", 50000, extra=[flagged])
        flagged["trusted"] = True  # once an analyst clears it, it counts
        self.check("low", "chidi", "airtime", 50000, extra=[flagged])

    def test_brand_new_customer_is_medium(self):
        row = {"timestamp": NOW, "amount": 1000, "transaction_type": "payment", "merchant_category": "airtime",
               "channel": "mobile_app", "device_id": "d", "country": "NG", "counterparty_account": ""}
        verdict = assess([row])
        self.assertEqual(level(verdict["probability"]), "medium")

    def test_reasons_explain_themselves(self):
        verdict = judge("chidi", "airtime", 50000)
        text = " ".join(verdict["reasons"])
        self.assertIn("₦50,000 airtime", text)
        self.assertIn("₦2,000", text)  # the largest airtime he has bought
        self.assertLessEqual(verdict["probability"], 0.99)

    def test_the_guide_matches_the_judgement(self):
        # The amounts printed in the presenter's guide must land in the band they claim.
        largest = 2000
        bands = amount_bands(largest)
        self.check("low", "chidi", "airtime", bands["low_up_to"])
        self.check("medium", "chidi", "airtime", bands["low_up_to"] + 1)
        self.check("medium", "chidi", "airtime", bands["medium_up_to"])
        self.check("high", "chidi", "airtime", bands["medium_up_to"] + 1)
        self.check("high", "chidi", "airtime", bands["critical_from"] - 1)
        self.check("critical", "chidi", "airtime", bands["critical_from"])


class PredictorShapeTests(unittest.TestCase):
    def test_same_answer_shape_as_the_ai_model(self):
        customer = CUSTOMERS[0]
        rows = history_rows(customer) + [{
            "timestamp": NOW, "amount": 50000, "transaction_type": "payment", "merchant_category": "airtime",
            "channel": "mobile_app", "device_id": customer["device"], "country": "NG", "counterparty_account": "",
        }]
        result = RulesPredictor().predict(rows)
        self.assertEqual(set(result), {"xgboost_score", "lstm_score", "fraud_probability", "model_version",
                                       "top_features", "processing_time_ms"})
        self.assertGreaterEqual(result["fraud_probability"], 0.85)


if __name__ == "__main__":
    unittest.main()
