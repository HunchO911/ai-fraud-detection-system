import { useState } from "react";
import { api } from "../lib/api.js";
import { money } from "../lib/format.js";
import RiskBadge from "./RiskBadge.jsx";

/**
 * Sends a real transaction to the API so you can watch the whole chain work:
 * save -> AI model scores it -> status set -> email / SMS alerts sent.
 *
 * "Everyday payment" copies the device, payee and country of a recent low-risk transaction,
 * so it looks normal. "Suspicious transfer" uses a new device, new country and a new payee.
 */
export default function TestTransaction({ baseline, onSent }) {
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [sent, setSent] = useState(null);

  const presets = {
    everyday: () => ({
      amount: amount || "4500.00",
      transaction_type: "payment",
      channel: baseline?.channel ?? "mobile_app",
      device_id: baseline?.device_id ?? "",
      counterparty_account: baseline?.counterparty_account ?? "",
      country: baseline?.country || "NG",
      city: baseline?.city || "",
    }),
    suspicious: () => ({
      amount: amount || "850000.00",
      transaction_type: "transfer",
      channel: "web",
      device_id: `unknown-${Math.random().toString(36).slice(2, 8)}`,
      counterparty_account: String(Math.floor(1e9 + Math.random() * 9e9)),
      country: "RU",
      city: "Moscow",
    }),
  };

  async function send(kind) {
    setBusy(true);
    setError(null);
    try {
      const created = await api.createTransaction(presets[kind]());
      setSent(created);
      onSent?.();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  const verdict = sent?.detection?.risk_level;

  return (
    <section className="panel" aria-labelledby="test-title">
      <div className="panel-head">
        <h2 id="test-title">Send a test transaction</h2>
        <span className="muted">Sent as you; scored by the AI model straight away</span>
      </div>
      <div className="panel-body test-box">
        <div className="test-actions">
          <label className="field" style={{ width: 170 }}>
            <span>Amount (optional)</span>
            <input className="input num" inputMode="decimal" placeholder="Preset amount" value={amount}
              onChange={(e) => setAmount(e.target.value.replace(/[^0-9.]/g, ""))} />
          </label>
          <button className="btn" disabled={busy} onClick={() => send("everyday")}>Everyday payment</button>
          <button className="btn btn-danger" disabled={busy} onClick={() => send("suspicious")}>Suspicious transfer</button>
        </div>
        {error && <div className="notice error" role="alert">{error.message}</div>}
        {sent && !error && (
          <div className="test-result" role="status">
            <strong>{sent.reference}</strong>
            <span className="num">{money(sent.amount, sent.currency)}</span>
            {verdict ? (
              <>
                <RiskBadge level={verdict} />
                <span className="muted">
                  {verdict === "high" || verdict === "critical"
                    ? "Flagged. Email and SMS alerts are on their way."
                    : "Approved. No alert needed."}
                </span>
              </>
            ) : (
              <span className="muted">Saved, not scored yet. Train the model, then run score_pending.</span>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
