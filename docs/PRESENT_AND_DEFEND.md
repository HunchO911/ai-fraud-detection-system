# How to present and defend the project

## The one-sentence pitch
"A banking app that checks every payment against the customer's own history in real time, and instantly alerts staff inside the dashboard when a payment doesn't fit."

## What to say the system does (60 seconds)
1. A customer makes a payment (airtime, data, bill, transfer, cash withdrawal).
2. Before it goes through, the backend looks up that customer's past payments.
3. It asks the question a bank clerk would: *is this normal for THIS person?* It compares the amount with the largest payment of the same kind they have made, and checks for a new device, a new country, a new account, odd hours and too many payments too fast.
4. It adds up points into a fraud score from 0 to 100% and a colour: green Low, yellow Medium, red High, dark red Critical.
5. High and Critical payments are **flagged and held**. A pop-up appears, the bell shows a number, and the payment appears on the Alerts page with the reasons in plain words.
6. An analyst opens the alert and marks it **fraud** (blocks it) or **false alarm** (approves it and teaches the system it is normal).

## Demo script (about 5 minutes)
Before you start: open the dashboard, sign in as **admin@example.com**, press **Customers** then **Reset demo data** so every number below is true.

1. **Customers page.** Show Chidi's history and the table: "He has bought airtime between ₦500 and ₦2,000. Up to ₦2,000 is Low, up to ₦6,000 is Medium, ₦20,000 and more is Critical. This is learned from his own history."
2. **Live page → Make a payment.** Customer Chidi, Buy airtime, **₦1,500** → green Low, "went through."
3. **₦5,000** → yellow Medium: unusual, but allowed.
4. **₦50,000** → Critical, flagged. Point at the pop-up, the bell, and the reason: "₦50,000 airtime is 25 times their largest airtime (₦2,000)."
5. **Send ₦50,000 again** → still Critical. "A flagged payment never becomes the new normal."
6. **Switch to Tunde** (student, small amounts). ₦50,000 airtime is Critical, but ₦500 is Low. "Same amount, different customers, different verdicts. That is what history-based means."
7. **Tunde pays an electricity bill of ₦5,000** → Medium: first time he has ever paid a bill.
8. **Tick "new unknown device" and "from abroad"** on Chidi with a normal amount → High. Signals add up.
9. **Bell → click the alert → Mark as false alarm.** Now that payment counts as normal.
10. Log in as **chidi@example.com** (same password) to show a customer sees only their own payments and only the risk level, never the score.

The exact amounts and results are in `DEMO_HISTORY.md`. Use that list; do not improvise amounts above a customer's usual maximum without checking it, because every Low payment that is accepted becomes part of their normal.

## Before presenting
- Press **Reset demo data** on the Customers page (or Manual Deploy on Render 20 to 30 minutes ahead). Open the site once so the server is awake. UptimeRobot keeps it awake.
- Have the Render URL and the GitHub repo open in case someone asks.

## Likely questions and honest answers

**"Where is the AI / machine learning?"**
Be direct. This version uses behavioural profiling with rules: it learns each customer's normal from their own history and scores deviations. I also built and trained an XGBoost + LSTM hybrid, and it is in the code (`fraud_engine/`). It is switched off in this demo (`FRAUD_ENGINE=rules`) because training needs a lot of data and time. It can be switched on with one setting. Do not say the demo is running the neural network, because it is not.

**"Why rules instead of ML?"**
They are transparent: every alert explains itself in plain words, which regulators and bank staff require. They work on day one with no training data, and they are fast. The trade-off is that the rules are chosen by hand. ML can find patterns people didn't think of, which is why the ML path is kept as a next step.

**"Is the data real?"**
No. All three customers and their payments are made-up (`detection/demo_data.py`). No real money moves and no real bank is connected. The phone numbers are fake.

**"How does it avoid being fooled by someone raising amounts slowly?"**
Anything above the largest payment ever made is at least Medium, and only Low-risk or analyst-cleared payments count as normal. A fraudster can't creep upward.

**"What about false positives, where a real customer is flagged?"**
That is what Medium (allowed) and the analyst review are for. A genuine large payment gets flagged, the analyst clears it as a false alarm, and it becomes part of the customer's normal.

**"Why not just block High risk automatically?"**
They are held for review. Blocking real customers is costly, so a human decides. That is standard practice. Critical payments could be auto-blocked with a one-line change.

**"Is it secure?"**
Login uses JWT tokens with refresh. Customers see only their own data and never the score. Staff-only pages are enforced on the server, not just hidden in the browser. The "pay as a customer" feature exists only for the demo (`DEMO_MODE`) and is switched off for a real deployment.

**"How would this scale?"**
The check reads one customer's recent history, which is a fast indexed database query. The server is stateless, so more copies can run behind a load balancer. For millions of customers, the history would be cached.

**"What are the limits?"** (say these before they are asked)
- Hand-tuned rules, tested only on made-up data.
- A brand-new customer has no history, so everything is Medium at first.
- Email and SMS alerts are built but switched off. Alerts appear inside the app.
- It is a simulation of banking, not a bank.

## The technology in one line each
React (dashboard) → Django REST API (backend, JWT login) → PostgreSQL (data) → history check (`fraud_engine/rules.py`) → alerts in the dashboard (bell, pop-ups, Alerts page). Hosted on Render (backend) and Vercel (dashboard).
