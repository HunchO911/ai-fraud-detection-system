import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api.js";
import { useAuth } from "../lib/auth.jsx";
import { Link, useRoute } from "../lib/router.jsx";
import { usePolling } from "../lib/usePolling.js";
import { clock, label, money } from "../lib/format.js";
import PulseStrip from "../components/PulseStrip.jsx";
import RiskBadge from "../components/RiskBadge.jsx";
import TestTransaction from "../components/TestTransaction.jsx";
import { Empty, ErrorNotice, Loading } from "../components/States.jsx";

const STATUS = { pending: "Scoring", approved: "Approved", flagged: "Flagged", blocked: "Blocked" };

function FeedRow({ txn, staff, fresh, onOpen }) {
  const level = txn.detection?.risk_level;
  const target = staff && txn.detection?.id;
  const className = `feed-row ${level ?? "unscored"}${fresh ? " fresh" : ""}${target ? " clickable" : ""}`;
  const place = [txn.city, txn.country].filter(Boolean).join(", ");

  const cells = (
    <>
      <span className="num muted">{clock(txn.timestamp)}</span>
      <span>
        <span className="cell-main">{staff ? txn.user_email : txn.reference}</span>
        {staff && <span className="cell-sub" style={{ display: "block" }}>{txn.reference}</span>}
      </span>
      <span className="cell-main num feed-amount">{money(txn.amount, txn.currency)}</span>
      <span>
        <span className="cell-main">{label(txn.transaction_type)}</span>
        <span className="cell-sub" style={{ display: "block" }}>
          {label(txn.channel)}{place ? ` · ${place}` : ""}
        </span>
      </span>
      <span>{level ? <RiskBadge level={level} /> : <span className="badge badge-plain">Scoring…</span>}</span>
      <span className="muted">{STATUS[txn.status] ?? txn.status}</span>
    </>
  );

  return (
    <li>
      {target ? (
        <button className={className} onClick={() => onOpen(txn.detection.id)} style={{ font: "inherit", color: "inherit" }}>
          {cells}
        </button>
      ) : (
        <div className={className}>{cells}</div>
      )}
    </li>
  );
}

export default function Live() {
  const { user, isStaff } = useAuth();
  const { navigate } = useRoute();
  const feed = usePolling(() => api.transactions({ page_size: 20 }), 3000, []);
  const stats = usePolling(() => api.stats(), 6000, []);

  // Highlight rows that appear after the first load.
  const seen = useRef(null);
  const [fresh, setFresh] = useState(() => new Set());
  useEffect(() => {
    if (!feed.data) return;
    const ids = feed.data.results.map((t) => t.id);
    if (seen.current === null) {
      seen.current = new Set(ids);
      return;
    }
    const novel = ids.filter((id) => !seen.current.has(id));
    if (novel.length) {
      novel.forEach((id) => seen.current.add(id));
      setFresh(new Set(novel));
    }
  }, [feed.data]);

  const rows = feed.data?.results ?? [];
  // The "Everyday payment" test copies a normal-looking transaction: the user's own newest
  // low-risk one if there is one, otherwise anyone's.
  const isLow = (t) => t.detection?.risk_level === "low";
  const baseline = rows.find((t) => isLow(t) && t.user_email === user.email) ?? rows.find(isLow);
  const s = stats.data;
  const onSent = () => {
    feed.refresh();
    stats.refresh();
    // The alert emails are sent a moment after the response; check again shortly.
    setTimeout(() => feed.refresh(), 1500);
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Live transactions</h1>
          {s ? (
            <p className="summary" style={{ color: "var(--ink)" }}>
              <b className="num">{s.transactions}</b> in the last 24 hours.{" "}
              <b className="num">{s.flagged}</b> flagged
              {isStaff && (
                <>
                  , <b className="num">{s.pending_review}</b>{" "}
                  {s.pending_review > 0 ? <Link to="/alerts">waiting for review</Link> : "waiting for review"}
                </>
              )}
              .
            </p>
          ) : (
            <p>Watching for new transactions.</p>
          )}
        </div>
        <span className={`live-dot${feed.error ? " stale" : ""}`} role="status">
          {feed.error ? "Connection lost, retrying" : feed.updatedAt ? `Live · updated ${clock(feed.updatedAt)}` : "Connecting"}
        </span>
      </div>

      {s && <PulseStrip hourly={s.hourly} />}

      <TestTransaction baseline={baseline} onSent={onSent} />

      <section className="panel" aria-labelledby="feed-title">
        <div className="panel-head">
          <h2 id="feed-title">Latest transactions</h2>
          <span className="muted">Newest first · refreshes every 3 seconds</span>
        </div>
        {feed.loading && !feed.data ? (
          <Loading text="Loading transactions…" />
        ) : feed.error && !feed.data ? (
          <div className="panel-body"><ErrorNotice error={feed.error} onRetry={feed.refresh} /></div>
        ) : rows.length === 0 ? (
          <Empty title="No transactions yet">Send a test transaction above and it will appear here.</Empty>
        ) : (
          <>
            <div className="feed-head" aria-hidden="true">
              <span>Time</span><span>{isStaff ? "Customer" : "Reference"}</span>
              <span className="feed-amount">Amount</span><span>Details</span><span>Risk</span><span>Status</span>
            </div>
            <ul className="feed">
              {rows.map((t) => (
                <FeedRow key={t.id} txn={t} staff={isStaff} fresh={fresh.has(t.id)}
                  onOpen={(id) => navigate(`/alerts/${id}`)} />
              ))}
            </ul>
          </>
        )}
      </section>
    </>
  );
}
