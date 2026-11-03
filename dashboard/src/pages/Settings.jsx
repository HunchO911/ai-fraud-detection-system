import { useEffect, useState } from "react";
import { api } from "../lib/api.js";
import { dateTime, percent } from "../lib/format.js";
import ScoreScale from "../components/ScoreScale.jsx";
import { ErrorNotice, Loading } from "../components/States.jsx";

const LEVELS = [
  ["medium", "Medium and above"],
  ["high", "High and above"],
  ["critical", "Critical only"],
];
const THRESHOLDS = [
  ["medium_threshold", "Medium starts at"],
  ["high_threshold", "High starts at"],
  ["critical_threshold", "Critical starts at"],
];
const FLAGS = [
  ["email_alerts_enabled", "Send email alerts", "Email the people chosen below when a transaction reaches the email level."],
  ["sms_alerts_enabled", "Send SMS alerts", "Text the people chosen below when a transaction reaches the SMS level."],
  ["notify_customer", "Tell the customer", "The account holder gets a short warning about their own transaction."],
  ["notify_analysts", "Tell analysts and admins", "Staff get the full details and a link to review it."],
];

/** Server values -> form values (thresholds shown as whole percentages). */
const toForm = (s) => ({
  ...s,
  medium_threshold: String(Math.round(s.medium_threshold * 100)),
  high_threshold: String(Math.round(s.high_threshold * 100)),
  critical_threshold: String(Math.round(s.critical_threshold * 100)),
});
const FIELDS = [
  ...THRESHOLDS.map(([k]) => k),
  ...FLAGS.map(([k]) => k),
  "email_min_risk",
  "sms_min_risk",
];

export default function Settings() {
  const [saved, setSaved] = useState(null); // what the server has
  const [form, setForm] = useState(null); // what is on screen
  const [loadError, setLoadError] = useState(null);
  const [saveError, setSaveError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  const load = () => {
    setLoadError(null);
    api.settings().then((s) => { setSaved(s); setForm(toForm(s)); }).catch(setLoadError);
  };
  useEffect(load, []);

  if (loadError && !saved) return <ErrorNotice error={loadError} onRetry={load} />;
  if (!form) return <Loading text="Loading settings…" />;

  const original = toForm(saved);
  const dirty = FIELDS.some((k) => form[k] !== original[k]);
  const set = (key, value) => { setForm((f) => ({ ...f, [key]: value })); setDone(false); };

  const m = Number(form.medium_threshold) / 100;
  const h = Number(form.high_threshold) / 100;
  const c = Number(form.critical_threshold) / 100;
  const ordered = m > 0 && m < h && h < c && c <= 1 && [m, h, c].every(Number.isFinite);

  async function save(event) {
    event.preventDefault();
    if (!ordered) return;
    setBusy(true);
    setSaveError(null);
    const body = {};
    FIELDS.forEach((k) => {
      if (form[k] !== original[k]) {
        body[k] = k.endsWith("_threshold") ? Math.round(Number(form[k])) / 100 : form[k];
      }
    });
    try {
      const next = await api.saveSettings(body);
      setSaved(next);
      setForm(toForm(next));
      setDone(true);
    } catch (e) {
      setSaveError(e);
    } finally {
      setBusy(false);
    }
  }

  const model = saved.model_status ?? {};

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Settings</h1>
          <p>Choose how sensitive the detector is and who gets told. Changes apply to the next transaction.</p>
        </div>
      </div>

      <form className="settings-grid" onSubmit={save}>
        <div className="stack">
          <section className="panel" aria-labelledby="levels-title">
            <div className="panel-head"><h2 id="levels-title">Risk levels</h2></div>
            <div className="panel-body stack" style={{ gap: 18 }}>
              <p className="muted">
                The model gives each transaction a fraud probability. These points decide where it becomes medium, high or critical risk.
              </p>
              <div className="form-grid">
                {THRESHOLDS.map(([key, text]) => (
                  <label key={key} className="field">
                    <span>{text}</span>
                    <span className="input-suffix">
                      <input className="input num" inputMode="numeric" value={form[key]}
                        onChange={(e) => set(key, e.target.value.replace(/[^0-9]/g, "").slice(0, 3))} />
                    </span>
                  </label>
                ))}
              </div>
              {ordered ? (
                <ScoreScale thresholds={{ medium: m, high: h, critical: c }} />
              ) : (
                <div className="notice error" role="alert">
                  The levels must rise from medium to high to critical, between 1% and 100%.
                </div>
              )}
            </div>
          </section>

          <section className="panel" aria-labelledby="who-title">
            <div className="panel-head"><h2 id="who-title">Alerts</h2></div>
            <div className="panel-body">
              {FLAGS.map(([key, title, hint]) => (
                <label key={key} className="toggle">
                  <input type="checkbox" checked={form[key]} onChange={(e) => set(key, e.target.checked)} />
                  <span><b>{title}</b><small>{hint}</small></span>
                </label>
              ))}
              <div className="form-grid" style={{ marginTop: 16, gridTemplateColumns: "repeat(2, minmax(0, 1fr))" }}>
                {[["email_min_risk", "Email from"], ["sms_min_risk", "SMS from"]].map(([key, text]) => (
                  <label key={key} className="field">
                    <span>{text}</span>
                    <select className="input" value={form[key]} onChange={(e) => set(key, e.target.value)}>
                      {LEVELS.map(([value, name]) => <option key={value} value={value}>{name}</option>)}
                    </select>
                  </label>
                ))}
              </div>
            </div>
          </section>

          {saveError && <div className="notice error" role="alert">{saveError.message}</div>}
          <div className="save-bar">
            <button className="btn btn-primary" disabled={!dirty || !ordered || busy}>
              {busy ? "Saving…" : "Save changes"}
            </button>
            {done && <span className="notice ok" role="status">Saved</span>}
            {!dirty && !done && <span className="muted">No changes to save</span>}
          </div>
        </div>

        <section className="panel" aria-labelledby="model-title">
          <div className="panel-head"><h2 id="model-title">AI model</h2></div>
          <div className="panel-body">
            {model.available ? (
              <dl className="meta-list">
                <div><dt>Version</dt><dd>{model.version}</dd></div>
                <div><dt>Trained</dt><dd>{dateTime(model.trained_at)}</dd></div>
                <div><dt>Trained on</dt><dd>{model.n_transactions?.toLocaleString()} transactions</dd></div>
                <div><dt>Data</dt><dd>{model.data_source}</dd></div>
                <div><dt>Precision</dt><dd>{model.hybrid_precision != null ? percent(model.hybrid_precision) : "—"}</dd></div>
                <div><dt>Recall</dt><dd>{model.hybrid_recall != null ? percent(model.hybrid_recall) : "—"}</dd></div>
              </dl>
            ) : (
              <div className="notice info">
                No trained model found. Run <code>python -m fraud_engine.train</code> in the backend folder, then restart the server.
                Until then, new transactions are saved as “Scoring”.
              </div>
            )}
            {saved.updated_by_email && (
              <p className="muted" style={{ marginTop: 16, fontSize: "0.88rem" }}>
                Settings last changed by {saved.updated_by_email} on {dateTime(saved.updated_at)}.
              </p>
            )}
          </div>
        </section>
      </form>
    </>
  );
}
