import { RISK, riskLabel } from "../lib/risk.js";

/** Coloured pill with the risk word in it (colour is never the only signal). */
export default function RiskBadge({ level }) {
  return (
    <span className={`badge risk-${level}`} title={RISK[level]?.hint}>
      {riskLabel(level)}
    </span>
  );
}
