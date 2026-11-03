/**
 * A bar from 0% to 100% split into the four risk zones, with an optional marker.
 * `thresholds` are fractions: where medium, high and critical begin.
 */
export default function ScoreScale({ probability, thresholds }) {
  const { medium, high, critical } = thresholds;
  const pct = (x) => `${Math.max(0, Math.min(1, x)) * 100}%`;
  const width = (from, to) => `${Math.max(0, Math.min(1, to) - Math.min(1, from)) * 100}%`;
  const hasMarker = typeof probability === "number";

  return (
    <div className="scale">
      <div className="scale-track" role={hasMarker ? "img" : "presentation"}
        aria-label={hasMarker ? `Fraud probability ${Math.round(probability * 100)}%` : undefined}>
        <span className="seg-low" style={{ width: width(0, medium) }} />
        <span className="seg-medium" style={{ width: width(medium, high) }} />
        <span className="seg-high" style={{ width: width(high, critical) }} />
        <span className="seg-critical" style={{ width: width(critical, 1) }} />
        {hasMarker && <i className="scale-marker" style={{ left: pct(probability) }} />}
      </div>
      <div className="scale-ticks" aria-hidden="true">
        <span style={{ left: 0 }}>0%</span>
        <span style={{ left: pct(medium) }}>{Math.round(medium * 100)}%</span>
        <span style={{ left: pct(high) }}>{Math.round(high * 100)}%</span>
        <span style={{ left: pct(critical) }}>{Math.round(critical * 100)}%</span>
        <span style={{ left: "100%" }}>100%</span>
      </div>
    </div>
  );
}

export const DEFAULT_THRESHOLDS = { medium: 0.3, high: 0.6, critical: 0.85 };
