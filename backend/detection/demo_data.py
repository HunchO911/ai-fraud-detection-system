"""
The three demo customers and their payment history, written by hand.

This is plain data (no Django here) so that three things always agree:
    * `python manage.py seed_demo` saves it into the database,
    * the tests check what the history check says about it,
    * the list you present from (docs/DEMO_HISTORY.md) is built from it.

Each history line is:  (days ago, hour of the day in Lagos time, what for, amount in naira, account paid)
"What for" is one of: airtime, data, electricity, transfer, withdrawal.
"""

COUNTRY = "NG"
CITY = "Lagos"

# What each kind of payment looks like in the database.
# purpose -> (transaction_type, merchant_category, merchant_name, channel)
PURPOSES = {
    "airtime": ("payment", "airtime", "Airtime top-up", "mobile_app"),
    "data": ("payment", "data", "Data bundle", "mobile_app"),
    "electricity": ("payment", "electricity", "Electricity bill", "mobile_app"),
    "transfer": ("transfer", "", "", "mobile_app"),
    "withdrawal": ("withdrawal", "", "ATM withdrawal", "atm"),
}

# Names for the accounts the customers have paid before (shown on the dashboard).
PAYEE_NAMES = {
    "0123456789": "Mum",
    "0456789012": "Friend (Emeka)",
    "0234567890": "Supplier A",
    "0345678901": "Supplier B",
    "0567890123": "Parents",
    "0678901234": "Friend (Seun)",
}

CUSTOMERS = [
    {
        "email": "chidi@example.com",
        "first_name": "Chidi",
        "last_name": "Okafor",
        "phone": "+2340000000003",
        "device": "chidi-iphone-13",
        "about": "Salaried worker. Buys airtime and data often, pays electricity, sends money to his mum.",
        "history": [
            (44, 9, "airtime", 1000, ""),
            (41, 18, "transfer", 25000, "0123456789"),
            (38, 12, "electricity", 15000, ""),
            (35, 10, "data", 3500, ""),
            (33, 19, "airtime", 500, ""),
            (30, 13, "transfer", 30000, "0123456789"),
            (27, 9, "airtime", 2000, ""),
            (24, 16, "electricity", 12000, ""),
            (21, 11, "data", 3500, ""),
            (18, 20, "airtime", 1000, ""),
            (15, 14, "transfer", 5000, "0456789012"),
            (12, 10, "airtime", 1000, ""),
            (9, 17, "electricity", 18000, ""),
            (7, 12, "data", 3500, ""),
            (5, 15, "transfer", 20000, "0123456789"),
            (3, 9, "airtime", 500, ""),
            (1, 18, "airtime", 2000, ""),
        ],
    },
    {
        "email": "ngozi@example.com",
        "first_name": "Ngozi",
        "last_name": "Eze",
        "phone": "+2340000000004",
        "device": "ngozi-samsung-a54",
        "about": "Small-business owner. Large transfers to two suppliers, bills, cash withdrawals.",
        "history": [
            (43, 10, "transfer", 150000, "0234567890"),
            (40, 14, "electricity", 35000, ""),
            (38, 9, "airtime", 5000, ""),
            (36, 11, "transfer", 90000, "0345678901"),
            (33, 13, "withdrawal", 50000, ""),
            (31, 16, "transfer", 200000, "0234567890"),
            (28, 10, "data", 10000, ""),
            (26, 15, "electricity", 40000, ""),
            (23, 12, "transfer", 180000, "0234567890"),
            (20, 9, "withdrawal", 40000, ""),
            (18, 17, "airtime", 10000, ""),
            (15, 11, "transfer", 120000, "0345678901"),
            (12, 14, "electricity", 38000, ""),
            (10, 10, "withdrawal", 60000, ""),
            (8, 12, "transfer", 250000, "0234567890"),
            (5, 9, "airtime", 5000, ""),
            (2, 16, "data", 10000, ""),
        ],
    },
    {
        "email": "tunde@example.com",
        "first_name": "Tunde",
        "last_name": "Bello",
        "phone": "+2340000000005",
        "device": "tunde-tecno-spark",
        "about": "Student on a small budget. Small airtime and data top-ups, small transfers. Has never paid a bill.",
        "history": [
            (36, 10, "airtime", 200, ""),
            (33, 15, "airtime", 300, ""),
            (30, 12, "data", 1000, ""),
            (27, 18, "transfer", 5000, "0567890123"),
            (24, 9, "airtime", 500, ""),
            (21, 14, "airtime", 200, ""),
            (18, 11, "data", 1500, ""),
            (15, 16, "transfer", 3000, "0678901234"),
            (12, 10, "airtime", 300, ""),
            (9, 13, "withdrawal", 5000, ""),
            (6, 19, "data", 1000, ""),
            (4, 12, "airtime", 500, ""),
            (2, 15, "transfer", 10000, "0567890123"),
        ],
    },
]
