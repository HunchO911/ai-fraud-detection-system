/** Risk levels: wording and colour class. Colour is never the only signal; the word is always shown too. */

export const RISK = {
  low: { label: "Low", hint: "Looks normal for this customer" },
  medium: { label: "Medium", hint: "A little unusual; worth a look if time allows" },
  high: { label: "High", hint: "Likely fraud; an analyst should review it" },
  critical: { label: "Critical", hint: "Very likely fraud; review it now" },
};

export const riskLabel = (level) => RISK[level]?.label ?? level;

/** Plain-language names for the model's signals (see fraud_engine/config.py). */
const FEATURES = {
  amount: "Transaction amount",
  log_amount: "Transaction amount",
  amount_zscore: "Amount is unusual for this customer",
  amount_sum_24h: "Total spent in the last 24 hours",
  hour_sin: "Time of day",
  hour_cos: "Time of day",
  is_night: "Made at night",
  is_weekend: "Made at the weekend",
  log_gap_seconds: "Time since their previous transaction",
  txn_count_1h: "Transactions in the last hour",
  txn_count_24h: "Transactions in the last 24 hours",
  new_device: "First time on this device",
  new_country: "First time from this country",
  new_counterparty: "First time paying this account",
  type_transfer: "Transaction type: transfer",
  type_payment: "Transaction type: payment",
  type_withdrawal: "Transaction type: withdrawal",
  type_deposit: "Transaction type: deposit",
};

export function featureLabel(name) {
  if (FEATURES[name]) return FEATURES[name];
  if (name.startsWith("channel_")) return `Channel: ${name.slice(8).replace(/_/g, " ")}`;
  const text = name.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** top_features -> [{ name, text, value, raises }] sorted by strength; positive value raises the risk. */
export function explainFeatures(topFeatures = {}) {
  return Object.entries(topFeatures)
    .map(([name, value]) => ({ name, text: featureLabel(name), value, raises: value > 0 }))
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value));
}
