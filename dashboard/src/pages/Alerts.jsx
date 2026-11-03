import { useEffect, useState } from "react";
import { api } from "../lib/api.js";
import { Link } from "../lib/router.jsx";
import { usePolling } from "../lib/usePolling.js";
import { dateTime, label, money, percent, timeAgo } from "../lib/format.js";
import RiskBadge from "../components/RiskBadge.jsx";
import Pagination from "../components/Pagination.jsx";
import { Empty, ErrorNotice, Loading } from "../components/States.jsx";

const FILTERS = [
  { key: "review", text: "Needs review", params: { risk: "high,critical", review: "pending" } },
  { key: "serious", text: "High and critical", params: { risk: "high,critical" } },
  { key: "medium", text: "Medium", params: { risk: "medium" } },
  { key: "low", text: "Low", params: { risk: "low" } },
  { key: "all", text: "All", params: {} },
];
const REVIEW = { pending: "Not reviewed", confirmed_fraud: "Fraud confirmed", false_positive: "False alarm" };
const PAGE_SIZE = 25;

export default function Alerts() {
  const [filter, setFilter] = useState("review");
  const [text, setText] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  // Wait until typing pauses before asking the server.
  useEffect(() => {
    const t = setTimeout(() => setSearch(text.trim()), 300);
    return () => clearTimeout(t);
  }, [text]);

  const active = FILTERS.find((f) => f.key === filter);
  const list = usePolling(
    () => api.detections({ ...active.params, search, page, page_size: PAGE_SIZE }),
    10000,
    [filter, search, page],
  );
  const rows = list.data?.results ?? [];

  const pick = (key) => { setFilter(key); setPage(1); };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Alerts</h1>
          <p>Every scored transaction, newest first. Green is low risk, yellow is medium, red is high or critical.</p>
        </div>
      </div>

      <div className="toolbar">
        <div className="chips" role="group" aria-label="Filter alerts">
          {FILTERS.map((f) => (
            <button key={f.key} className="chip" aria-pressed={filter === f.key} onClick={() => pick(f.key)}>
              {f.text}
            </button>
          ))}
        </div>
        <input className="input search" type="search" placeholder="Search reference or email" aria-label="Search alerts"
          value={text} onChange={(e) => { setText(e.target.value); setPage(1); }} />
      </div>

      <section className="panel" aria-label="Alert list">
        {list.loading && !list.data ? (
          <Loading text="Loading alerts…" />
        ) : list.error && !list.data ? (
          <div className="panel-body"><ErrorNotice error={list.error} onRetry={list.refresh} /></div>
        ) : rows.length === 0 ? (
          <Empty title={filter === "review" && !search ? "Nothing is waiting for review" : "No alerts match"}>
            {filter === "review" && !search ? (
              <button className="btn btn-sm" onClick={() => pick("all")}>Show all alerts</button>
            ) : (
              "Try another filter or clear the search."
            )}
          </Empty>
        ) : (
          <>
            {rows.map((d) => (
              <Link key={d.id} to={`/alerts/${d.id}`} className={`alert-row ${d.risk_level}`}>
                <span><RiskBadge level={d.risk_level} /></span>
                <span>
                  <span className="cell-main">{d.transaction.user_email}</span>
                  <span className="cell-sub" style={{ display: "block" }}>{d.transaction.reference}</span>
                </span>
                <span className="cell-main num">{money(d.transaction.amount, d.transaction.currency)}</span>
                <span>
                  <span className="cell-main">{label(d.transaction.transaction_type)} · {percent(d.fraud_probability)} fraud</span>
                  <span className="cell-sub" style={{ display: "block" }} title={dateTime(d.created_at)}>{timeAgo(d.created_at)}</span>
                </span>
                <span className="muted">{label(d.transaction.status)}</span>
                <span className="muted">{REVIEW[d.review_status] ?? d.review_status}</span>
              </Link>
            ))}
            <Pagination page={page} count={list.data.count} size={PAGE_SIZE} onPage={setPage} />
          </>
        )}
      </section>
    </>
  );
}
