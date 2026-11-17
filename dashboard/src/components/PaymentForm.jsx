import { useEffect, useState } from "react";
import { api } from "../lib/api.js";
import { useAuth } from "../lib/auth.jsx";
import { money, naira, percent } from "../lib/format.js";
import { explainFeatures } from "../lib/risk.js";
import RiskBadge from "./RiskBadge.jsx";

/** What the customer is paying for, and how that is saved (the history check compares like with like). */
export const PURPOSES = [
  { key: "airtime", label: "Buy airtime", shape: { transaction_type: "payment", merchant_category: "airtime", merchant_name: "Airtime top-up", channel: "mobile_app" } },
  { key: "data", label: "Buy a data bundle", shape: { transaction_type: "payment", merchant_category: "data", merchant_name: "Data bundle", channel: "mobile_app" } },
  { key: "electricity", label: "Pay an electricity bill", shape: { transaction_type: "payment", merchant_category: "electricity", merchant_name: "Electricity bill", channel: "mobile_app" } },
  { key: "transfer", label: "Send money to an account", shape: { transaction_type: "transfer", channel: "mobile_app" } },
  { key: "withdrawal", label: "Withdraw cash (ATM)", shape: { transaction_type: "withdrawal", merchant_name: "ATM withdrawal", channel: "atm" } },
];

const randomDigits = (n) => Array.from({ length: n }, () => Math.floor(Math.random() * 10)).join("");

/** One sentence about what is normal for this customer and this kind of payment. */
function usualText(profile, purpose) {
  const entry = profile?.purposes.find((p) => p.key === purpose);
  if (!entry) return null;
  if (!entry.count) return "They have never made this kind of payment before.";
  return `They usually pay ${naira(entry.smallest)} to ${naira(entry.largest)} (${entry.count} payment${entry.count === 1 ? "" : "s"} so far).`;
}

/**
 * Makes a payment for a customer. The server compares it with that customer's own history
 * and answers with a risk level; a risky payment is flagged and shows up in the bell and on the Alerts page.
 * Staff can pay "as" any demo customer, so one login is enough to show all of them.
 */
export default function PaymentForm({ onSent }) {
  const { isStaff } = useAuth();
  const [customers, setCustomers] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [who, setWho] = useState("");
  const [purpose, setPurpose] = useState("airtime");
  const [amount, setAmount] = useState("");
  const [payee, setPayee] = useState("");
  const [newDevice, setNewDevice] = useState(false);
  const [abroad, setAbroad] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const loadCustomers = () =>
    api.customers().then((list) => {
      setCustomers(list);
      setWho((current) => current || list[0]?.email || "");
    }).catch(setLoadError);
  useEffect(() => { loadCustomers(); }, []);

  const profile = customers?.find((c) => c.email === who);
  // For transfers: pick an account they have paid before, or a brand-new one.
  useEffect(() => {
    setPayee(profile?.payees[0]?.account ?? "new");
  }, [who, customers?.length]); // eslint-disable-line react-hooks/exhaustive-deps

  async function pay(event) {
    event.preventDefault();
    if (!profile || !Number(amount)) return;
    setBusy(true);
    setError(null);
    setResult(null);
    const chosen = PURPOSES.find((p) => p.key === purpose);
    const body = {
      ...chosen.shape,
      amount: Number(amount).toFixed(2),
      device_id: newDevice ? `unknown-${Math.random().toString(36).slice(2, 8)}` : profile.usual_device,
      country: abroad ? "RU" : profile.usual_country,
      city: abroad ? "Moscow" : profile.usual_city,
      counterparty_account: purpose === "transfer" ? (payee === "new" ? randomDigits(10) : payee) : "",
    };
    if (isStaff) body.on_behalf_of = who;
    try {
      const created = await api.createTransaction(body);
      // Staff can read the full explanation straight away.
      const detail = isStaff && created.detection?.id ? await api.detection(created.detection.id).catch(() => null) : null;
      setResult({ txn: created, detail, who: profile.name });
      onSent?.();
      loadCustomers(); // the profile may have changed
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  const level = result?.txn.detection?.risk_level;
  const flagged = level === "high" || level === "critical";
  const reasons = result?.detail ? explainFeatures(result.detail.top_features).slice(0, 4) : [];

  return (
    <section className="panel" aria-labelledby="pay-title">
      <div className="panel-head">
        <h2 id="pay-title">Make a payment</h2>
        <span className="muted">Checked against the customer's own history straight away</span>
      </div>
      <form className="panel-body pay-box" onSubmit={pay}>
        {loadError && <div className="notice error" role="alert">{loadError.message}</div>}
        <div className="pay-grid">
          {isStaff && (
            <label className="field">
              <span>Customer</span>
              <select className="input" value={who} onChange={(e) => { setWho(e.target.value); setResult(null); }}>
                {(customers ?? []).map((c) => <option key={c.email} value={c.email}>{c.name} ({c.email})</option>)}
              </select>
            </label>
          )}
          <label className="field">
            <span>What is it for?</span>
            <select className="input" value={purpose} onChange={(e) => { setPurpose(e.target.value); setResult(null); }}>
              {PURPOSES.map((p) => <option key={p.key} value={p.key}>{p.label}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Amount (₦)</span>
            <input className="input num" inputMode="decimal" placeholder="e.g. 50000" value={amount}
              onChange={(e) => setAmount(e.target.value.replace(/[^0-9.]/g, ""))} />
          </label>
          {purpose === "transfer" && (
            <label className="field">
              <span>Send to</span>
              <select className="input" value={payee} onChange={(e) => setPayee(e.target.value)}>
                {(profile?.payees ?? []).map((p) => (
                  <option key={p.account} value={p.account}>{p.name || "Paid before"} · {p.account}</option>
                ))}
                <option value="new">A new account (never paid before)</option>
              </select>
            </label>
          )}
        </div>

        {profile && <p className="pay-usual muted">{usualText(profile, purpose)}</p>}

        <div className="pay-options">
          <label className="check"><input type="checkbox" checked={newDevice} onChange={(e) => setNewDevice(e.target.checked)} /> Use a new, unknown device</label>
          <label className="check"><input type="checkbox" checked={abroad} onChange={(e) => setAbroad(e.target.checked)} /> Pay from abroad (Moscow)</label>
          <button className="btn btn-primary" disabled={busy || !profile || !Number(amount)}>{busy ? "Checking…" : "Pay now"}</button>
        </div>

        {error && <div className="notice error" role="alert">{error.message}</div>}
        {result && !error && (
          <div className={`pay-result ${level ?? ""}`} role="status">
            <div className="pay-result-top">
              <strong className="num">{money(result.txn.amount, result.txn.currency)}</strong>
              <span>{result.who}</span>
              {level ? <RiskBadge level={level} /> : <span className="badge badge-plain">Not scored</span>}
              {result.detail && <span className="muted num">{percent(result.detail.fraud_probability)} fraud score</span>}
            </div>
            <p>
              {!level
                ? "The payment was saved but could not be checked."
                : flagged
                  ? "Flagged and held for review. The alert is in the bell at the top and on the Alerts page."
                  : level === "medium"
                    ? "Went through, but it is a little unusual for this customer."
                    : "Went through. This is normal for this customer."}
            </p>
            {reasons.length > 0 && (
              <ul className="pay-reasons">
                {reasons.map((r) => <li key={r.name} className={r.raises ? "up" : "down"}>{r.text}</li>)}
              </ul>
            )}
          </div>
        )}
      </form>
    </section>
  );
}
