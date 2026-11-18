/**
 * Demo mode: the whole "server" runs inside the browser.
 *
 * It answers exactly the requests the dashboard normally sends to the Django API (same names,
 * same shapes), using the same history check and the same three customers. There is no server and
 * no database. Payments are kept in this browser (localStorage), so a refresh keeps them, and
 * "Reset demo data" on the Customers page puts everything back.
 *
 * Switched on with VITE_DEMO=true when the dashboard is built (see the README).
 */

import { CITY, COUNTRY, CUSTOMERS, PAYEE_NAMES, PURPOSES } from "./data.js";
import { amountBands, assess, MODEL_VERSION, purposeName, purposeOf } from "./rules.js";

const STORE_KEY = "fraudwatch.demo.v1";
const HOUR = 3600 * 1000;
const DAY = 24 * HOUR;
const PURPOSE_ORDER = ["airtime", "data", "electricity", "transfer", "withdrawal"];

const USERS = [
  { id: "1", email: "admin@example.com", role: "admin", first_name: "Ada", last_name: "Admin" },
  { id: "2", email: "analyst@example.com", role: "analyst", first_name: "Amina", last_name: "Analyst" },
  ...CUSTOMERS.map((c, i) => ({ id: String(10 + i), email: c.email, role: "customer", first_name: c.first_name, last_name: c.last_name })),
].map((u) => ({ ...u, full_name: `${u.first_name} ${u.last_name}` }));

const DEFAULT_SETTINGS = {
  medium_threshold: 0.3, high_threshold: 0.6, critical_threshold: 0.85,
  email_alerts_enabled: false, sms_alerts_enabled: false, email_min_risk: "high", sms_min_risk: "critical",
  notify_customer: true, notify_analysts: true, updated_at: null, updated_by_email: null,
};
const MODEL_STATUS = {
  available: true, engine: "rules", version: MODEL_VERSION,
  description: "Compares every payment with the customer's own history: the usual amount for that kind of payment, known devices, countries and payees, time of day and speed.",
};

const uuid = () => (crypto.randomUUID ? crypto.randomUUID() : "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => ((Math.random() * 16) | 0).toString(16)));
const iso = (ms) => new Date(ms).toISOString();

/* ---------------------------------------------------------------- state */

let state = null;

function levelOf(p, s) {
  return p >= s.critical_threshold ? "critical" : p >= s.high_threshold ? "high" : p >= s.medium_threshold ? "medium" : "low";
}

function addTransaction(s, email, body, { at = Date.now(), seed = false } = {}) {
  const txn = {
    id: uuid(), reference: `TXN-${uuid().replace(/-/g, "").slice(0, 16).toUpperCase()}`, user_email: email,
    amount: Number(body.amount).toFixed(2), currency: "NGN", transaction_type: body.transaction_type, channel: body.channel,
    merchant_name: body.merchant_name || "", merchant_category: body.merchant_category || "",
    counterparty_account: body.counterparty_account || "", device_id: body.device_id || "", ip_address: "102.89.1.5",
    country: body.country || "", city: body.city || "", timestamp: iso(at), created_at: iso(Date.now()), status: "approved",
  };
  let probability = 0.02;
  let reasons = { "Part of the customer's established history (demo data)": -0.1 };
  if (!seed) {
    const history = s.transactions
      .filter((t) => t.user_email === email)
      .sort((a, b) => a.timestamp.localeCompare(b.timestamp))
      .map((t) => asRow(s, t));
    ({ probability, reasons } = assess([...history, asRow(s, txn)]));
  }
  const level = levelOf(probability, s.settings);
  txn.status = level === "high" || level === "critical" ? "flagged" : "approved";
  const detection = {
    id: uuid(), created_at: txn.created_at, fraud_probability: probability, risk_level: level, review_status: "pending",
    model_version: seed ? "seed-history" : MODEL_VERSION, xgboost_score: probability, lstm_score: null, top_features: reasons,
    processing_time_ms: 1, reviewed_by_email: null, reviewed_at: null, review_notes: "", txn_id: txn.id, alerts: [],
  };
  txn._det = detection.id;
  s.transactions.push(txn);
  s.detections[detection.id] = detection;
  return txn;
}

/** A transaction as the history check wants to see it. */
function asRow(s, t) {
  return {
    timestamp: new Date(t.timestamp).getTime(), amount: Number(t.amount), transaction_type: t.transaction_type,
    merchant_category: t.merchant_category, device_id: t.device_id, country: t.country,
    counterparty_account: t.counterparty_account, trusted: isTrusted(s, t),
  };
}

/** Only low-risk or analyst-cleared payments count as "normal" (same rule as the server). */
function isTrusted(s, t) {
  if (t.status !== "approved") return false;
  const d = s.detections[t._det];
  return !d || d.risk_level === "low" || d.review_status === "false_positive";
}

function seedState(settings = { ...DEFAULT_SETTINGS }) {
  const s = { transactions: [], detections: {}, settings };
  const now = Date.now();
  for (const c of CUSTOMERS) {
    for (const h of c.history) {
      // "days ago, at this hour in Lagos (UTC+1)"
      const day = new Date(now - h.daysAgo * DAY);
      const at = Date.UTC(day.getUTCFullYear(), day.getUTCMonth(), day.getUTCDate(), h.hour - 1);
      const shape = PURPOSES[h.purpose];
      addTransaction(
        s, c.email,
        { amount: h.amount, ...shape, device_id: c.device, country: COUNTRY, city: CITY, counterparty_account: h.payee },
        { at, seed: true },
      );
    }
  }
  return s;
}

function load() {
  if (state) return state;
  try {
    const raw = localStorage.getItem(STORE_KEY);
    if (raw) state = JSON.parse(raw);
  } catch {
    /* storage blocked or corrupt: start fresh */
  }
  if (!state?.transactions) state = seedState();
  return state;
}

function save() {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(state));
  } catch {
    /* private window: the demo still works until the page is reloaded */
  }
}

/* ---------------------------------------------------------------- helpers */

const pause = (ms = 120) => new Promise((resolve) => setTimeout(resolve, ms));
const isStaff = (u) => u.role === "admin" || u.role === "analyst";

function paginate(items, params, map) {
  const size = Math.min(Number(params?.page_size) || 25, 100);
  const page = Number(params?.page) || 1;
  const start = (page - 1) * size;
  return { count: items.length, next: null, previous: null, results: items.slice(start, start + size).map(map) };
}

function txnOut(s, t, staff) {
  const d = s.detections[t._det];
  const { _det, ...out } = t;
  out.detection = staff
    ? { id: d.id, fraud_probability: d.fraud_probability, risk_level: d.risk_level, review_status: d.review_status }
    : { risk_level: d.risk_level };
  return out;
}

const brief = (t) => ({
  id: t.id, reference: t.reference, user_email: t.user_email, amount: t.amount, currency: t.currency,
  transaction_type: t.transaction_type, channel: t.channel, country: t.country, city: t.city, timestamp: t.timestamp, status: t.status,
});

function profile(s, email) {
  const u = USERS.find((x) => x.email === email);
  const mine = s.transactions.filter((t) => t.user_email === email && isTrusted(s, t)).sort((a, b) => b.timestamp.localeCompare(a.timestamp));
  const rows = mine.map((t) => ({ purpose: purposeOf(t), amount: Number(t.amount), when: t.timestamp, payee: t.counterparty_account, device: t.device_id, country: t.country, city: t.city }));
  const common = (values, fallback = "") => {
    const counts = {};
    values.filter(Boolean).forEach((v) => (counts[v] = (counts[v] || 0) + 1));
    return Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? fallback;
  };
  const purposes = PURPOSE_ORDER.map((key) => {
    const amounts = rows.filter((r) => r.purpose === key).map((r) => r.amount);
    const entry = { key, label: purposeName(key).charAt(0).toUpperCase() + purposeName(key).slice(1), count: amounts.length };
    if (amounts.length) {
      const largest = Math.max(...amounts);
      Object.assign(entry, { smallest: Math.min(...amounts), largest, ...amountBands(largest) });
    }
    return entry;
  });
  const payees = [...new Set(rows.filter((r) => r.purpose === "transfer" && r.payee).map((r) => r.payee))].sort();
  return {
    id: u.id, email, name: u.full_name, usual_device: common(rows.map((r) => r.device)), usual_country: common(rows.map((r) => r.country), COUNTRY),
    usual_city: common(rows.map((r) => r.city)), transactions: rows.length, purposes,
    payees: payees.map((account) => ({ account, name: PAYEE_NAMES[account] || "" })),
    recent: rows.slice(0, 8).map((r) => ({ when: r.when, purpose: purposeName(r.purpose), amount: r.amount, payee: r.payee })),
  };
}

/* ---------------------------------------------------------------- the API */

export function createDemoApi({ ApiError, getTokens }) {
  const fail = (status, detail) => new ApiError(status, { detail }, detail);

  /** Who is signed in: the "access token" in demo mode is just `demo:<email>`. */
  function current() {
    const email = String(getTokens()?.access || "").replace(/^demo:/, "");
    const user = USERS.find((u) => u.email === email);
    if (!user) throw fail(401, "Your session has ended. Sign in again.");
    return user;
  }
  const staffOnly = (user) => {
    if (!isStaff(user)) throw fail(403, "You don't have permission to do that.");
  };

  return {
    async login(email) {
      await pause();
      const user = USERS.find((u) => u.email === String(email).trim().toLowerCase());
      // Demo mode has no real passwords: any password works for the demo accounts.
      if (!user) throw fail(401, "Email or password is wrong.");
      return { access: `demo:${user.email}`, refresh: "demo-refresh", user };
    },
    async logout() {},
    async me() {
      return current();
    },

    async transactions(params) {
      const user = current();
      const s = load();
      const items = s.transactions
        .filter((t) => isStaff(user) || t.user_email === user.email)
        .sort((a, b) => b.timestamp.localeCompare(a.timestamp));
      return paginate(items, params, (t) => txnOut(s, t, isStaff(user)));
    },

    async createTransaction(body) {
      const user = current();
      const s = load();
      await pause(250);
      let owner = user.email;
      if (body.on_behalf_of) {
        const customer = USERS.find((u) => u.email === String(body.on_behalf_of).toLowerCase() && u.role === "customer");
        if (!isStaff(user) || !customer) throw new ApiError(400, { on_behalf_of: "No customer with that email." }, "No customer with that email.");
        owner = customer.email;
      }
      const txn = addTransaction(s, owner, body);
      save();
      return txnOut(s, txn, isStaff(user));
    },

    async stats() {
      const user = current();
      const s = load();
      const items = s.transactions.filter((t) => isStaff(user) || t.user_email === user.email);
      const now = Date.now();
      const recent = items.filter((t) => new Date(t.timestamp).getTime() >= now - DAY);
      const flaggedOf = (list) => list.filter((t) => ["high", "critical"].includes(s.detections[t._det].risk_level));
      const flagged = flaggedOf(recent);
      const top = Math.floor(now / HOUR) * HOUR;
      const hourly = Array.from({ length: 24 }, (_, i) => {
        const start = top - (23 - i) * HOUR;
        const inHour = recent.filter((t) => { const at = new Date(t.timestamp).getTime(); return at >= start && at < start + HOUR; });
        return { hour: iso(start), total: inHour.length, flagged: flaggedOf(inHour).length };
      });
      const risk_counts = { low: 0, medium: 0, high: 0, critical: 0 };
      recent.forEach((t) => { risk_counts[s.detections[t._det].risk_level] += 1; });
      return {
        window_hours: 24, transactions: recent.length, flagged: flagged.length,
        pending_review: flagged.filter((t) => s.detections[t._det].review_status === "pending").length, risk_counts, hourly,
      };
    },

    async customers() {
      const user = current();
      const s = load();
      const emails = isStaff(user) ? CUSTOMERS.map((c) => c.email) : [user.email];
      return emails.map((email) => profile(s, email));
    },

    async resetDemo() {
      const user = current();
      if (user.role !== "admin") throw fail(403, "You don't have permission to do that.");
      state = seedState(load().settings);
      save();
      return { status: "reset" };
    },

    async detections(params = {}) {
      staffOnly(current());
      const s = load();
      let items = Object.values(s.detections).filter((d) => d.model_version !== "seed-history" || params.risk || params.review || params.search);
      if (params.risk) items = items.filter((d) => params.risk.split(",").includes(d.risk_level));
      if (params.review) items = items.filter((d) => d.review_status === params.review);
      const find = (d) => s.transactions.find((t) => t.id === d.txn_id);
      if (params.search) {
        const q = String(params.search).toLowerCase();
        items = items.filter((d) => find(d).reference.toLowerCase().includes(q) || find(d).user_email.includes(q));
      }
      items.sort((a, b) => b.created_at.localeCompare(a.created_at));
      return paginate(items, params, (d) => ({
        id: d.id, created_at: d.created_at, fraud_probability: d.fraud_probability, risk_level: d.risk_level,
        review_status: d.review_status, model_version: d.model_version, transaction: brief(find(d)),
      }));
    },

    async detection(id) {
      staffOnly(current());
      return detail(load(), id);
    },

    async review(id, body) {
      const user = current();
      staffOnly(user);
      const s = load();
      const d = s.detections[id];
      if (!d) throw fail(404, "That item no longer exists.");
      if (!["pending", "confirmed_fraud", "false_positive"].includes(body.review_status)) throw fail(400, "That is not a valid decision.");
      d.review_status = body.review_status;
      d.review_notes = body.review_notes || "";
      d.reviewed_by_email = body.review_status === "pending" ? null : user.email;
      d.reviewed_at = body.review_status === "pending" ? null : iso(Date.now());
      const t = s.transactions.find((x) => x.id === d.txn_id);
      t.status = { confirmed_fraud: "blocked", false_positive: "approved" }[body.review_status] ?? "flagged";
      save();
      return detail(s, id);
    },

    async settings() {
      if (current().role !== "admin") throw fail(403, "You don't have permission to do that.");
      return { ...load().settings, model_status: MODEL_STATUS };
    },

    async saveSettings(body) {
      const user = current();
      if (user.role !== "admin") throw fail(403, "You don't have permission to do that.");
      const s = load();
      const merged = { ...s.settings, ...body };
      if (!(0 < merged.medium_threshold && merged.medium_threshold < merged.high_threshold && merged.high_threshold < merged.critical_threshold && merged.critical_threshold <= 1)) {
        throw new ApiError(400, null, "Risk levels must rise from medium to high to critical, and stay between 0 and 1.");
      }
      s.settings = { ...merged, updated_at: iso(Date.now()), updated_by_email: user.email };
      save();
      return { ...s.settings, model_status: MODEL_STATUS };
    },
  };

  function detail(s, id) {
    const d = s.detections[id];
    if (!d) throw fail(404, "That item no longer exists.");
    const t = s.transactions.find((x) => x.id === d.txn_id);
    const { txn_id, ...out } = d;
    return {
      ...out,
      transaction: { ...brief(t), merchant_name: t.merchant_name, merchant_category: t.merchant_category, counterparty_account: t.counterparty_account, device_id: t.device_id, ip_address: t.ip_address },
      thresholds: { medium: s.settings.medium_threshold, high: s.settings.high_threshold, critical: s.settings.critical_threshold },
    };
  }
}
