/* GENERATED from backend/detection/demo_data.py. Edit that file, not this one. */
const DATA = {
  "COUNTRY": "NG",
  "CITY": "Lagos",
  "PURPOSES": {
    "airtime": {
      "transaction_type": "payment",
      "merchant_category": "airtime",
      "merchant_name": "Airtime top-up",
      "channel": "mobile_app"
    },
    "data": {
      "transaction_type": "payment",
      "merchant_category": "data",
      "merchant_name": "Data bundle",
      "channel": "mobile_app"
    },
    "electricity": {
      "transaction_type": "payment",
      "merchant_category": "electricity",
      "merchant_name": "Electricity bill",
      "channel": "mobile_app"
    },
    "transfer": {
      "transaction_type": "transfer",
      "merchant_category": "",
      "merchant_name": "",
      "channel": "mobile_app"
    },
    "withdrawal": {
      "transaction_type": "withdrawal",
      "merchant_category": "",
      "merchant_name": "ATM withdrawal",
      "channel": "atm"
    }
  },
  "PAYEE_NAMES": {
    "0123456789": "Mum",
    "0456789012": "Friend (Emeka)",
    "0234567890": "Supplier A",
    "0345678901": "Supplier B",
    "0567890123": "Parents",
    "0678901234": "Friend (Seun)"
  },
  "CUSTOMERS": [
    {
      "email": "chidi@example.com",
      "first_name": "Chidi",
      "last_name": "Okafor",
      "phone": "+2340000000003",
      "device": "chidi-iphone-13",
      "history": [
        {
          "daysAgo": 44,
          "hour": 9,
          "purpose": "airtime",
          "amount": 1000,
          "payee": ""
        },
        {
          "daysAgo": 41,
          "hour": 18,
          "purpose": "transfer",
          "amount": 25000,
          "payee": "0123456789"
        },
        {
          "daysAgo": 38,
          "hour": 12,
          "purpose": "electricity",
          "amount": 15000,
          "payee": ""
        },
        {
          "daysAgo": 35,
          "hour": 10,
          "purpose": "data",
          "amount": 3500,
          "payee": ""
        },
        {
          "daysAgo": 33,
          "hour": 19,
          "purpose": "airtime",
          "amount": 500,
          "payee": ""
        },
        {
          "daysAgo": 30,
          "hour": 13,
          "purpose": "transfer",
          "amount": 30000,
          "payee": "0123456789"
        },
        {
          "daysAgo": 27,
          "hour": 9,
          "purpose": "airtime",
          "amount": 2000,
          "payee": ""
        },
        {
          "daysAgo": 24,
          "hour": 16,
          "purpose": "electricity",
          "amount": 12000,
          "payee": ""
        },
        {
          "daysAgo": 21,
          "hour": 11,
          "purpose": "data",
          "amount": 3500,
          "payee": ""
        },
        {
          "daysAgo": 18,
          "hour": 20,
          "purpose": "airtime",
          "amount": 1000,
          "payee": ""
        },
        {
          "daysAgo": 15,
          "hour": 14,
          "purpose": "transfer",
          "amount": 5000,
          "payee": "0456789012"
        },
        {
          "daysAgo": 12,
          "hour": 10,
          "purpose": "airtime",
          "amount": 1000,
          "payee": ""
        },
        {
          "daysAgo": 9,
          "hour": 17,
          "purpose": "electricity",
          "amount": 18000,
          "payee": ""
        },
        {
          "daysAgo": 7,
          "hour": 12,
          "purpose": "data",
          "amount": 3500,
          "payee": ""
        },
        {
          "daysAgo": 5,
          "hour": 15,
          "purpose": "transfer",
          "amount": 20000,
          "payee": "0123456789"
        },
        {
          "daysAgo": 3,
          "hour": 9,
          "purpose": "airtime",
          "amount": 500,
          "payee": ""
        },
        {
          "daysAgo": 1,
          "hour": 18,
          "purpose": "airtime",
          "amount": 2000,
          "payee": ""
        }
      ]
    },
    {
      "email": "ngozi@example.com",
      "first_name": "Ngozi",
      "last_name": "Eze",
      "phone": "+2340000000004",
      "device": "ngozi-samsung-a54",
      "history": [
        {
          "daysAgo": 43,
          "hour": 10,
          "purpose": "transfer",
          "amount": 150000,
          "payee": "0234567890"
        },
        {
          "daysAgo": 40,
          "hour": 14,
          "purpose": "electricity",
          "amount": 35000,
          "payee": ""
        },
        {
          "daysAgo": 38,
          "hour": 9,
          "purpose": "airtime",
          "amount": 5000,
          "payee": ""
        },
        {
          "daysAgo": 36,
          "hour": 11,
          "purpose": "transfer",
          "amount": 90000,
          "payee": "0345678901"
        },
        {
          "daysAgo": 33,
          "hour": 13,
          "purpose": "withdrawal",
          "amount": 50000,
          "payee": ""
        },
        {
          "daysAgo": 31,
          "hour": 16,
          "purpose": "transfer",
          "amount": 200000,
          "payee": "0234567890"
        },
        {
          "daysAgo": 28,
          "hour": 10,
          "purpose": "data",
          "amount": 10000,
          "payee": ""
        },
        {
          "daysAgo": 26,
          "hour": 15,
          "purpose": "electricity",
          "amount": 40000,
          "payee": ""
        },
        {
          "daysAgo": 23,
          "hour": 12,
          "purpose": "transfer",
          "amount": 180000,
          "payee": "0234567890"
        },
        {
          "daysAgo": 20,
          "hour": 9,
          "purpose": "withdrawal",
          "amount": 40000,
          "payee": ""
        },
        {
          "daysAgo": 18,
          "hour": 17,
          "purpose": "airtime",
          "amount": 10000,
          "payee": ""
        },
        {
          "daysAgo": 15,
          "hour": 11,
          "purpose": "transfer",
          "amount": 120000,
          "payee": "0345678901"
        },
        {
          "daysAgo": 12,
          "hour": 14,
          "purpose": "electricity",
          "amount": 38000,
          "payee": ""
        },
        {
          "daysAgo": 10,
          "hour": 10,
          "purpose": "withdrawal",
          "amount": 60000,
          "payee": ""
        },
        {
          "daysAgo": 8,
          "hour": 12,
          "purpose": "transfer",
          "amount": 250000,
          "payee": "0234567890"
        },
        {
          "daysAgo": 5,
          "hour": 9,
          "purpose": "airtime",
          "amount": 5000,
          "payee": ""
        },
        {
          "daysAgo": 2,
          "hour": 16,
          "purpose": "data",
          "amount": 10000,
          "payee": ""
        }
      ]
    },
    {
      "email": "tunde@example.com",
      "first_name": "Tunde",
      "last_name": "Bello",
      "phone": "+2340000000005",
      "device": "tunde-tecno-spark",
      "history": [
        {
          "daysAgo": 36,
          "hour": 10,
          "purpose": "airtime",
          "amount": 200,
          "payee": ""
        },
        {
          "daysAgo": 33,
          "hour": 15,
          "purpose": "airtime",
          "amount": 300,
          "payee": ""
        },
        {
          "daysAgo": 30,
          "hour": 12,
          "purpose": "data",
          "amount": 1000,
          "payee": ""
        },
        {
          "daysAgo": 27,
          "hour": 18,
          "purpose": "transfer",
          "amount": 5000,
          "payee": "0567890123"
        },
        {
          "daysAgo": 24,
          "hour": 9,
          "purpose": "airtime",
          "amount": 500,
          "payee": ""
        },
        {
          "daysAgo": 21,
          "hour": 14,
          "purpose": "airtime",
          "amount": 200,
          "payee": ""
        },
        {
          "daysAgo": 18,
          "hour": 11,
          "purpose": "data",
          "amount": 1500,
          "payee": ""
        },
        {
          "daysAgo": 15,
          "hour": 16,
          "purpose": "transfer",
          "amount": 3000,
          "payee": "0678901234"
        },
        {
          "daysAgo": 12,
          "hour": 10,
          "purpose": "airtime",
          "amount": 300,
          "payee": ""
        },
        {
          "daysAgo": 9,
          "hour": 13,
          "purpose": "withdrawal",
          "amount": 5000,
          "payee": ""
        },
        {
          "daysAgo": 6,
          "hour": 19,
          "purpose": "data",
          "amount": 1000,
          "payee": ""
        },
        {
          "daysAgo": 4,
          "hour": 12,
          "purpose": "airtime",
          "amount": 500,
          "payee": ""
        },
        {
          "daysAgo": 2,
          "hour": 15,
          "purpose": "transfer",
          "amount": 10000,
          "payee": "0567890123"
        }
      ]
    }
  ]
};

export const { COUNTRY, CITY, PURPOSES, PAYEE_NAMES, CUSTOMERS } = DATA;
