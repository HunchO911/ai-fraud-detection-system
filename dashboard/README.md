# Fraud Watch: React dashboard

Login, live transaction monitor, colour-coded alert list, alert detail with analyst
review, and admin settings. Talks to the Django backend over its REST API.

| Page | Who | What it does |
|---|---|---|
| `/login` | everyone | Email and password; JWT is kept and refreshed automatically |
| `/` Live | everyone | Last 24 hours, live feed (polls every 3 s), **Send a test transaction** |
| `/alerts` | analyst, admin | Filter (needs review / high and critical / medium / low / all), search, pages |
| `/alerts/<id>` | analyst, admin | Fraud score, why the model scored it, emails/SMS sent, confirm fraud or false alarm |
| `/settings` | admin | Risk thresholds, email/SMS on-off and levels, who is told, model status |

Colours: green = low, yellow = medium, red = high, dark red = critical. The risk word is
always shown too, so colour is never the only signal.

## Run it

You need Node 20 or newer, and the Django backend running on port 8000.

```bash
cd dashboard
npm install
npm run dev          # http://localhost:5173
```

In development Vite forwards `/api` to `http://127.0.0.1:8000` (see `vite.config.js`), so
there is nothing to configure. For a production build, copy `.env.example` to `.env`, set
`VITE_API_URL` to your API address, run `npm run build`, and serve the `dist/` folder.
Add that address to `CORS_ALLOWED_ORIGINS` in the backend `.env`.

## Try the whole chain

1. Backend: `python manage.py seed_demo`, train the model, `python manage.py runserver`.
2. Sign in as `chidi@example.com` (password `Demo-Passw0rd!`) and press
   **Suspicious transfer**. The row appears as red, and the email/SMS alerts print in the
   backend terminal (or go out for real if you configured them).
3. Sign in as `analyst@example.com` to review it, and `admin@example.com` for Settings.

## Code map

```
src/lib/api.js        every API call; token storage; single refresh on 401; friendly errors
src/lib/auth.jsx      who is signed in
src/lib/router.jsx    small History-API router (no extra library)
src/lib/usePolling.js the "live" behaviour
src/lib/risk.js       risk wording, plain-language names for model signals
src/pages/            Login, Live, Alerts, AlertDetail, Settings
src/components/       Shell, RiskBadge, ScoreScale, PulseStrip, TestTransaction, ...
```
