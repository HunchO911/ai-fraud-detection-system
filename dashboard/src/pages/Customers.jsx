import { useState } from "react";
import { api } from "../lib/api.js";
import { useAuth } from "../lib/auth.jsx";
import { dateTime, money, naira } from "../lib/format.js";
import { usePolling } from "../lib/usePolling.js";
import { ErrorNotice, Loading } from "../components/States.jsx";

/** The other things the check looks at, besides the amount. */
const OTHER_SIGNALS = [
  ["A device they have never used", "+30%"],
  ["A country they have never paid from", "+30%"],
  ["A kind of payment they have never made", "+30%"],
  ["A new account on a transfer", "+15%"],
  ["Late at night (00:00 to 05:59), when they never are", "+10%"],
  ["4 payments in an hour / 6 or more", "+30% / +60%"],
];

function Guide({ entry }) {
  if (!entry.count) {
    return (
      <tr>
        <td><b>{entry.label}</b></td>
        <td colSpan={5} className="muted">Never made. The first one is Medium, and a large one is flagged.</td>
      </tr>
    );
  }
  return (
    <tr>
      <td><b>{entry.label}</b><span className="cell-sub" style={{ display: "block" }}>{entry.count} payment{entry.count === 1 ? "" : "s"}</span></td>
      <td className="num">{naira(entry.smallest)} to {naira(entry.largest)}</td>
      <td className="num"><span className="band low">up to {naira(entry.low_up_to)}</span></td>
      <td className="num"><span className="band medium">up to {naira(entry.medium_up_to)}</span></td>
      <td className="num"><span className="band high">up to {naira(entry.critical_from - 1)}</span></td>
      <td className="num"><span className="band critical">{naira(entry.critical_from)} and more</span></td>
    </tr>
  );
}

function CustomerPanel({ c }) {
  return (
    <section className="panel" aria-label={c.name}>
      <div className="panel-head">
        <div>
          <h2>{c.name}</h2>
          <span className="muted">{c.email} · {c.transactions} trusted payments · usual device {c.usual_device} · {c.usual_country}</span>
        </div>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table className="table guide">
          <thead>
            <tr>
              <th>Kind of payment</th><th>Usual range</th>
              <th>Low</th><th>Medium</th><th>High (flagged)</th><th>Critical (flagged)</th>
            </tr>
          </thead>
          <tbody>{c.purposes.map((p) => <Guide key={p.key} entry={p} />)}</tbody>
        </table>
      </div>
      <div className="panel-body cust-extra">
        <div>
          <h3>Accounts they have paid before</h3>
          {c.payees.length === 0 ? <p className="muted">None</p> : (
            <ul className="plain">{c.payees.map((p) => <li key={p.account}><span className="num">{p.account}</span> {p.name && <span className="muted">· {p.name}</span>}</li>)}</ul>
          )}
        </div>
        <div>
          <h3>Latest payments</h3>
          <ul className="plain">
            {c.recent.map((r, i) => (
              <li key={i}><span className="num">{naira(r.amount)}</span> {r.purpose} <span className="muted">· {dateTime(r.when)}</span></li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

export default function Customers() {
  const { isAdmin } = useAuth();
  const list = usePolling(() => api.customers(), 0, []);
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function reset() {
    setBusy(true);
    setError(null);
    try {
      await api.resetDemo();
      setAsking(false);
      list.refresh();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Customers</h1>
          <p>
            What is normal for each customer, built from their own payment history. A new payment is compared with the
            largest payment of the same kind they have made before. Anything above that is at least Medium. These bands are for the amount alone; the signals at the bottom add to it.
          </p>
        </div>
        {isAdmin && (
          asking ? (
            <span className="reset-ask">
              Delete the payments made during the demo and restore the original history?
              <button className="btn btn-sm btn-danger" disabled={busy} onClick={reset}>{busy ? "Resetting…" : "Yes, reset"}</button>
              <button className="btn btn-sm" disabled={busy} onClick={() => setAsking(false)}>Cancel</button>
            </span>
          ) : (
            <button className="btn btn-sm" onClick={() => setAsking(true)}>Reset demo data</button>
          )
        )}
      </div>
      {error && <div className="notice error" role="alert">{error.message}</div>}

      {list.loading && !list.data ? <Loading text="Loading customers…" /> :
        list.error && !list.data ? <ErrorNotice error={list.error} onRetry={list.refresh} /> : (
          <>
            {list.data.map((c) => <CustomerPanel key={c.id} c={c} />)}
            <section className="panel" aria-labelledby="other-title">
              <div className="panel-head"><h2 id="other-title">Other things that raise the score</h2><span className="muted">Added to the amount's score. Medium starts at 30%, High at 60%, Critical at 85%.</span></div>
              <div className="panel-body">
                <ul className="plain signals">
                  {OTHER_SIGNALS.map(([text, points]) => <li key={text}><span>{text}</span><b className="num">{points}</b></li>)}
                </ul>
                <p className="muted" style={{ marginTop: 12 }}>
                  Only payments that were low risk, or cleared by an analyst, count as "normal". A flagged payment never becomes the new normal.
                </p>
              </div>
            </section>
          </>
        )}
    </>
  );
}
