/** The last 24 hours as bars: the red part of each bar is the flagged transactions. */
export default function PulseStrip({ hourly = [] }) {
  const peak = Math.max(1, ...hourly.map((h) => h.total));
  const hourLabel = (iso) => new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });

  return (
    <div className="panel pulse">
      <div className="pulse-bars" role="img"
        aria-label={`Transactions per hour over the last 24 hours, ${hourly.reduce((n, h) => n + h.flagged, 0)} flagged`}>
        {hourly.map((h) => (
          <div key={h.hour} className={`pulse-col${h.total === 0 ? " empty" : ""}`}
            title={`${hourLabel(h.hour)}: ${h.total} transactions, ${h.flagged} flagged`}>
            {h.flagged > 0 && <div className="bad" style={{ height: `${(h.flagged / peak) * 100}%` }} />}
            {h.total - h.flagged > 0 && <div className="ok" style={{ height: `${((h.total - h.flagged) / peak) * 100}%` }} />}
          </div>
        ))}
      </div>
      <div className="pulse-axis">
        <span>{hourly.length ? hourLabel(hourly[0].hour) : ""}</span>
        <span className="legend">
          <span><i style={{ background: "var(--accent)", opacity: 0.45 }} />Transactions</span>
          <span><i style={{ background: "var(--high)" }} />Flagged</span>
        </span>
        <span>now</span>
      </div>
    </div>
  );
}
