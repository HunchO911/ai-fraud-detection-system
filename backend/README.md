# Fraud Detection: Django backend (Step 1)

Django 5.2 + Django REST Framework + PostgreSQL + JWT (SimpleJWT).

| App | Purpose |
|---|---|
| `authentication` | Custom `User` (email login, roles), registration, JWT login / refresh / logout |
| `transactions` | `Transaction` model and API to submit and list transactions |
| `detection` | `DetectionResult` model: hybrid XGBoost + LSTM scores, risk level, analyst review |
| `alerts` | `Alert` model: email / SMS notifications and their delivery status |

## 1. Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
```

Create the database (PostgreSQL must be running), then edit `.env` so the
`POSTGRES_*` values match your install:

```bash
psql -U postgres -c "CREATE DATABASE fraud_detection;"
```

## 2. Create the tables

The migration files are not included yet, so generate them first. Commit them
afterwards.

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser   # asks for email, first name, last name, password
python manage.py runserver
```

Admin panel: http://127.0.0.1:8000/admin/

## 3. Run the tests

```bash
python manage.py test --settings=config.test_settings   # no PostgreSQL needed (uses SQLite)
python manage.py test                                    # against PostgreSQL (needs CREATEDB rights)
```

## 4. Try the API

| Method | URL | Auth | What it does |
|---|---|---|---|
| POST | `/api/auth/register/` | none | Create a customer account, returns user + tokens |
| POST | `/api/auth/login/` | none | `{"email","password"}` returns `access`, `refresh`, `user` |
| POST | `/api/auth/token/refresh/` | none | `{"refresh"}` returns a new `access` and a new `refresh` |
| POST | `/api/auth/logout/` | Bearer | `{"refresh"}` revokes that refresh token |
| GET / PATCH | `/api/auth/me/` | Bearer | Read or update your profile |
| POST | `/api/transactions/` | Bearer | Submit a transaction |
| GET | `/api/transactions/` | Bearer | List (customers see their own, analysts and admins see all) |
| GET | `/api/transactions/<id>/` | Bearer | One transaction |

```bash
# Register
curl -X POST http://127.0.0.1:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"email":"ada@example.com","first_name":"Ada","last_name":"Obi","phone_number":"+2348012345678","password":"S3cure-Passw0rd!","password_confirm":"S3cure-Passw0rd!"}'

# Log in and copy the "access" value
curl -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"ada@example.com","password":"S3cure-Passw0rd!"}'

# Submit a transaction
curl -X POST http://127.0.0.1:8000/api/transactions/ \
  -H "Authorization: Bearer <access>" -H "Content-Type: application/json" \
  -d '{"amount":"25000.00","transaction_type":"transfer","channel":"mobile_app","counterparty_account":"0123456789","device_id":"device-abc","country":"NG","city":"Abuja"}'
```

Access tokens last 15 minutes and refresh tokens 7 days (`JWT_ACCESS_MINUTES`,
`JWT_REFRESH_DAYS` in `.env`). Refresh tokens rotate on every use.

## 5. Roles

Self-registration always creates a `customer`. To make an analyst, open
`/admin/` > Users, and change the user's **Role** to *Fraud analyst*.

## 6. Train the fraud model (Steps 3 and 4)

The AI code lives in `fraud_engine/` and does not need Django or a database.

```bash
pip install -r requirements-ml.txt      # TensorFlow needs Python 3.10-3.12 to be safe
python -m unittest fraud_engine.tests -v
python -m fraud_engine.train            # synthetic data; add --csv your_file.csv for real data
python -m fraud_engine.train --users 500 --epochs 5   # quick trial run
```

Training prints a PR-AUC / precision / recall table for XGBoost, the LSTM and the
hybrid on the newest 20% of transactions, then saves to `ml_artifacts/`:

| File | What it is |
|---|---|
| `xgboost_model.json` | XGBoost model |
| `lstm_model.keras` | LSTM model |
| `sequence_scaler.joblib` | Scaler for the LSTM inputs |
| `meta_model.joblib` | Logistic regression that combines the two scores |
| `metadata.json` | Feature lists, thresholds, metrics, library versions |

Load and score from Django (or a shell):

```python
from fraud_engine.predictor import get_predictor

result = get_predictor().predict(history)   # history = this customer's recent transactions,
                                            # newest last, columns = fraud_engine.config.RAW_COLUMNS
# result: xgboost_score, lstm_score, fraud_probability, model_version, top_features, processing_time_ms
```

Models are trained on synthetic data until you supply real labelled transactions
(`--csv`). Library versions must match between training and serving
(`metadata.json` records them).

## 7. Connect everything (AI scoring, alerts, dashboard API)

**What happens when a transaction arrives**

```
POST /api/transactions/  ->  saved (status "pending")
                         ->  detection.services.process_transaction()
                               builds the customer's history -> hybrid model -> DetectionResult
                               status becomes "approved" (low/medium) or "flagged" (high/critical)
                         ->  alerts.services.send_alerts()   (background thread after commit)
                               email and/or SMS, depending on risk level and the Settings page
```

If the model has not been trained, or anything in scoring fails, the transaction is still
saved as `pending` and the API still answers 201. After training, run
`python manage.py score_pending` to score what was missed.

**First run**

```bash
python manage.py makemigrations detection alerts   # new fields / DetectionSettings table
python manage.py migrate
python manage.py test                              # all tests
python manage.py seed_demo                         # demo users + history (needs requirements-ml.txt)
python -m fraud_engine.train                       # train the model (see section 6)
python manage.py runserver
```

`seed_demo` creates `admin@example.com`, `analyst@example.com`, `chidi@example.com` and
`ngozi@example.com`, all with password `Demo-Passw0rd!` (change it with `--password`).
Restart the server after training: the model is loaded once and kept in memory.

**New endpoints** (all need `Authorization: Bearer <access>`)

| Method and path | Who | What |
|---|---|---|
| `POST /api/transactions/` | any user | Create a transaction; it is scored immediately |
| `GET /api/transactions/` | any user | Live feed (customers: own only; includes `detection`) |
| `GET /api/dashboard/stats/` | any user | Last 24 hours: counts, risk counts, hourly buckets |
| `GET /api/detections/` | analyst, admin | Alert list. Filters: `risk=high,critical`, `review=pending`, `search=`, `ordering=`, `page`, `page_size` |
| `GET /api/detections/<id>/` | analyst, admin | Scores, reasons, alerts sent, review |
| `POST /api/detections/<id>/review/` | analyst, admin | `{"review_status": "confirmed_fraud" \| "false_positive" \| "pending", "review_notes": ""}` |
| `GET, PATCH /api/settings/` | admin | Risk thresholds, alert channels and audiences, model status |
| `GET /api/alerts/` | analyst, admin | Delivery log (email / SMS status) |

**Email and SMS**

Development default: both are printed in the terminal running `runserver`
(`EMAIL_BACKEND` console, `SMS_BACKEND=console`). To send for real, set in `.env`
(see `.env.example`): the `EMAIL_*` variables (any SMTP server, e.g. Gmail with an app
password) and `SMS_BACKEND=termii` with `TERMII_API_KEY` and `TERMII_SENDER_ID`.
The Termii call follows their documented API but has not been run against the live
service from here: send yourself one test SMS before relying on it.
Failed deliveries are recorded on the alert; retry them with
`python manage.py retry_failed_alerts`.

Who gets what is set on the dashboard's Settings page: email from *high* by default, SMS
from *critical*, to the customer and to analysts/admins. A user's own
`receive_email_alerts` / `receive_sms_alerts` flags and a stored phone number are respected.

**Things to know**

- Alerts are sent in a background thread so a slow mail server cannot slow the API
  (`ALERTS_ASYNC=False` sends them inline instead). For heavy traffic, move this to Celery.
- Set the `FRONTEND_URL` in `.env` to where the dashboard runs; analyst emails link to it.
- The dashboard runs on `http://localhost:5173`, already in `CORS_ALLOWED_ORIGINS`.

## What comes next

- Move alert sending to a task queue (Celery) for production traffic
- Retrain on real labelled transactions, and schedule retraining
- Real-time push (websockets) instead of the dashboard polling every 3 seconds
