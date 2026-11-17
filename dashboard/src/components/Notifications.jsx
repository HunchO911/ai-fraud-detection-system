import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api.js";
import { useAuth } from "../lib/auth.jsx";
import { Link, useRoute } from "../lib/router.jsx";
import { usePolling } from "../lib/usePolling.js";
import { money, timeAgo } from "../lib/format.js";
import { riskLabel } from "../lib/risk.js";
import RiskBadge from "./RiskBadge.jsx";

const FLAGGED = ["high", "critical"];
const TOAST_MS = 10000;

// "Last time the person opened the bell", remembered per user in this browser (optional: works without it).
const seenKey = (user) => `fraudwatch.alerts-seen.${user.id ?? user.email}`;
const readSeen = (user) => {
  try {
    return Number(localStorage.getItem(seenKey(user))) || null;
  } catch {
    return null;
  }
};
const writeSeen = (user, ms) => {
  try {
    localStorage.setItem(seenKey(user), String(ms));
  } catch {
    /* private window: the count just resets on reload */
  }
};

const describe = (t) => `${money(t.amount, t.currency)} ${(t.merchant_name || t.transaction_type).toLowerCase()}`;

/**
 * In-app alerts, no email or SMS needed.
 *   - a pop-up appears the moment a payment is flagged (High or Critical)
 *   - the bell shows how many flagged payments you have not looked at yet
 *   - opening the bell lists the latest ones
 * It watches the same transactions the Live page shows (every 3 seconds), so it works on every page.
 */
export default function Notifications() {
  const { user, isStaff } = useAuth();
  const { navigate } = useRoute();
  const feed = usePolling(() => api.transactions({ page_size: 30 }), 3000, []);
  const [open, setOpen] = useState(false);
  const [toasts, setToasts] = useState([]);
  const [seenAt, setSeenAt] = useState(() => readSeen(user) ?? Date.now());
  const known = useRef(null); // ids already seen, so only NEW flagged payments pop up
  const box = useRef(null);

  const flagged = (feed.data?.results ?? []).filter((t) => FLAGGED.includes(t.detection?.risk_level));
  const unread = flagged.filter((t) => new Date(t.created_at).getTime() > seenAt).length;

  // Pop up for flagged payments that appear after the first load.
  useEffect(() => {
    if (!feed.data) return;
    const ids = flagged.map((t) => t.id);
    if (known.current === null) {
      known.current = new Set(ids);
      return;
    }
    const fresh = flagged.filter((t) => !known.current.has(t.id));
    if (!fresh.length) return;
    fresh.forEach((t) => known.current.add(t.id));
    setToasts((list) => [...fresh.map((t) => ({ key: t.id, txn: t })), ...list].slice(0, 3));
    fresh.forEach((t) =>
      setTimeout(() => setToasts((list) => list.filter((x) => x.key !== t.id)), TOAST_MS),
    );
  }, [feed.data]); // eslint-disable-line react-hooks/exhaustive-deps

  // Close the list when clicking elsewhere or pressing Escape.
  useEffect(() => {
    if (!open) return;
    const away = (e) => { if (box.current && !box.current.contains(e.target)) setOpen(false); };
    const esc = (e) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  function toggle() {
    const next = !open;
    setOpen(next);
    if (next) {
      const now = Date.now();
      setSeenAt(now);
      writeSeen(user, now);
    }
  }

  const go = (t) => {
    setOpen(false);
    setToasts((list) => list.filter((x) => x.key !== t.id));
    if (isStaff && t.detection?.id) navigate(`/alerts/${t.detection.id}`);
  };

  return (
    <>
      <div className="bell-wrap" ref={box}>
        <button className="bell" onClick={toggle} aria-expanded={open} aria-haspopup="true"
          aria-label={unread ? `Alerts, ${unread} new` : "Alerts, none new"}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.7 21a2 2 0 0 1-3.4 0" />
          </svg>
          {unread > 0 && <span className="bell-count num">{unread > 9 ? "9+" : unread}</span>}
        </button>
        {open && (
          <div className="bell-menu" role="dialog" aria-label="Recent alerts">
            <div className="bell-head"><strong>Flagged payments</strong></div>
            {flagged.length === 0 ? (
              <p className="bell-empty muted">Nothing flagged. You will be told here the moment something is.</p>
            ) : (
              <ul>
                {flagged.slice(0, 8).map((t) => (
                  <li key={t.id}>
                    <button className={`bell-item ${t.detection.risk_level}`} onClick={() => go(t)}>
                      <span><RiskBadge level={t.detection.risk_level} /></span>
                      <span>
                        <span className="cell-main">{describe(t)}</span>
                        <span className="cell-sub" style={{ display: "block" }}>
                          {isStaff ? t.user_email : t.reference} · {timeAgo(t.created_at)}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {isStaff && <div className="bell-foot"><Link to="/alerts" onClick={() => setOpen(false)}>See all alerts</Link></div>}
          </div>
        )}
      </div>

      <div className="toasts" role="status" aria-live="polite">
        {toasts.map(({ key, txn }) => (
          <div key={key} className={`toast ${txn.detection.risk_level}`}>
            <button className="toast-body" onClick={() => go(txn)}>
              <strong>{riskLabel(txn.detection.risk_level)} risk: payment flagged</strong>
              <span>{describe(txn)}{isStaff ? ` · ${txn.user_email}` : ""}</span>
            </button>
            <button className="toast-x" aria-label="Dismiss" onClick={() => setToasts((l) => l.filter((x) => x.key !== key))}>×</button>
          </div>
        ))}
      </div>
    </>
  );
}
