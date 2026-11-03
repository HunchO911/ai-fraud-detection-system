import { useEffect, useState } from "react";
import { api } from "../lib/api.js";
import { Link } from "../lib/router.jsx";
import { dateTime, label, money, percent } from "../lib/format.js";
import { RISK, explainFeatures } from "../lib/risk.js";
import RiskBadge from "../components/RiskBadge.jsx";
import ScoreScale, { DEFAULT_THRESHOLDS } from "../components/ScoreScale.jsx";
import { ErrorNotice, Loading } from "../components/States.jsx";

const REVIEW_TEXT = {
  pending: "Not reviewed yet",
  confirmed_fraud: "Confirmed as fraud",
  false_positive: "Marked as a false alarm",
};

function Fact({ term, children }) {
  return (
    <div>
      <dt>{term}</dt>
      <dd>{children || "—"}</dd>
    </div>
  );
}

function ReviewPanel({ detection, onChange }) {
  const [notes, setNotes] = useState(detection.review_notes ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const reviewed = detection.review_status !== "pending";

  async function decide(review_status) {
    setBusy(true);
    setError(null);
    try {
      onChange(await api.review(detection.id, { review_status, review_notes: notes }));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="review-title">
      <div className="panel-head"><h2 id="review-title">Your decision</h2></div>
      <div className="panel-body">
        <div className="verdict" role="status">
          <strong>{REVIEW_TEXT[detection.review_status]}</strong>
          {reviewed && (
            <span className="muted" style={{ display: "block" }}>
              by {detection.reviewed_by_email} · {dateTime(detection.reviewed_at)}
            </span>
          )}
        </div>
        <label className="field" style={{ marginTop: 14 }}>
          <span>Notes (optional)</span>
          <textarea className="input" value={notes} maxLength={2000} onChange={(e) => setNotes(e.target.value)}
            placeholder="For example: customer confirmed by phone" />
        </label>
        {error && <div className="notice error" role="alert" style={{ marginTop: 12 }}>{error.message}</div>}
        <div className="review-actions">
          {detection.review_status !== "confirmed_fraud" && (
            <button className="btn btn-danger" disabled={busy} onClick={() => decide("confirmed_fraud")}>Confirm fraud</button>
          )}
          {detection.review_status !== "false_positive" && (
            <button className="btn" disabled={busy} onClick={() => decide("false_positive")}>Mark as false alarm</button>
          )}
          {reviewed && <button className="btn btn-quiet" disabled={busy} onClick={() => decide("pending")}>Reopen</button>}
        </div>
        <p className="muted" style={{ marginTop: 12, fontSize: "0.88rem" }}>
          Confirming fraud blocks the transaction. A false alarm approves it.
        </p>
      </div>
    </section>
  );
}

export default function AlertDetail({ id }) {
  const [detection, setDetection] = useState(null);
  const [error, setError] = useState(null);

  const load = () => {
    setError(null);
    api.detection(id).then(setDetection).catch(setError);
  };
  useEffect(() => {
    setDetection(null);
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (error && !detection) {
    return (
      <>
        <Link to="/alerts" className="back">← Back to alerts</Link>
        <ErrorNotice error={error} onRetry={load} />
      </>
    );
  }
  if (!detection) return <Loading text="Loading alert…" />;

  const t = detection.transaction;
  const reasons = explainFeatures(detection.top_features);
  const strongest = Math.max(0.0001, ...reasons.map((r) => Math.abs(r.value)));
  const thresholds = detection.thresholds ?? DEFAULT_THRESHOLDS;

  return (
    <>
      <Link to="/alerts" className="back">← Back to alerts</Link>
      <div className="page-head">
        <div>
          <h1>{money(t.amount, t.currency)} {label(t.transaction_type).toLowerCase()}</h1>
          <p>{t.reference} · {t.user_email} · {dateTime(t.timestamp)}</p>
        </div>
        <RiskBadge level={detection.risk_level} />
      </div>

      <div className="detail-top">
        <div className="stack">
          <section className="panel" aria-labelledby="score-title">
            <div className="panel-head"><h2 id="score-title">Fraud score</h2></div>
            <div className="panel-body">
              <div className="big-score">
                <strong className="num">{percent(detection.fraud_probability)}</strong>
                <span className="muted">{RISK[detection.risk_level]?.hint}</span>
              </div>
              <ScoreScale probability={detection.fraud_probability} thresholds={thresholds} />
              <dl className="facts" style={{ marginTop: 22 }}>
                <Fact term="Pattern model (XGBoost)">{percent(detection.xgboost_score)}</Fact>
                <Fact term="Sequence model (LSTM)">{percent(detection.lstm_score)}</Fact>
                <Fact term="Scored in">{`${detection.processing_time_ms} ms`}</Fact>
                <Fact term="Model version">{detection.model_version}</Fact>
              </dl>
            </div>
          </section>

          <section className="panel" aria-labelledby="why-title">
            <div className="panel-head">
              <h2 id="why-title">Why the model scored it this way</h2>
              <span className="muted">Red raises the risk, green lowers it</span>
            </div>
            <div className="panel-body">
              {reasons.length === 0 ? (
                <p className="muted">The model did not report reasons for this score.</p>
              ) : (
                <ul className="reasons">
                  {reasons.map((r) => (
                    <li key={r.name} className="reason">
                      <span>
                        <strong>{r.text}</strong>
                        <small>{r.raises ? "Raised the risk" : "Lowered the risk"}</small>
                      </span>
                      <span className="reason-bar" aria-hidden="true">
                        <i className={r.raises ? "up" : "down"} style={{ width: `${(Math.abs(r.value) / strongest) * 100}%` }} />
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>

          <section className="panel" aria-labelledby="notified-title">
            <div className="panel-head"><h2 id="notified-title">Notifications sent</h2></div>
            {detection.alerts.length === 0 ? (
              <div className="panel-body muted">
                No email or SMS was sent for this alert. This happens when the risk level is below the levels set on the Settings page.
              </div>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table className="table">
                  <thead>
                    <tr><th>Channel</th><th>To</th><th>Status</th><th>When</th></tr>
                  </thead>
                  <tbody>
                    {detection.alerts.map((a) => (
                      <tr key={a.id}>
                        <td>{label(a.channel)}</td>
                        <td>{a.destination}<span className="cell-sub" style={{ display: "block" }}>{a.recipient_email}</span></td>
                        <td>
                          <span className={`badge ${a.status === "sent" ? "risk-low" : a.status === "failed" ? "risk-high" : "badge-plain"}`}>
                            {label(a.status)}
                          </span>
                          {a.error_message && <span className="cell-sub" style={{ display: "block" }}>{a.error_message}</span>}
                        </td>
                        <td className="muted">{dateTime(a.sent_at || a.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>

        <div className="stack">
          <ReviewPanel key={detection.review_status} detection={detection} onChange={setDetection} />
          <section className="panel" aria-labelledby="txn-title">
            <div className="panel-head"><h2 id="txn-title">Transaction</h2></div>
            <div className="panel-body">
              <dl className="facts">
                <Fact term="Customer">{t.user_email}</Fact>
                <Fact term="Status">{label(t.status)}</Fact>
                <Fact term="Channel">{label(t.channel)}</Fact>
                <Fact term="Paid to account">{t.counterparty_account}</Fact>
                <Fact term="Device">{t.device_id}</Fact>
                <Fact term="Location">{[t.city, t.country].filter(Boolean).join(", ")}</Fact>
                <Fact term="IP address">{t.ip_address}</Fact>
                <Fact term="Merchant">{t.merchant_name}</Fact>
              </dl>
            </div>
          </section>
        </div>
      </div>
    </>
  );
}
