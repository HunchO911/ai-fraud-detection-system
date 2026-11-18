/**
 * The history check, in JavaScript. A line-for-line port of backend/fraud_engine/rules.py,
 * used by demo mode so the dashboard can score payments without a server.
 *
 * Question asked of every new payment: "is this normal for THIS customer?"
 * Points are added up (0 to 1). See the table at the top of rules.py for the full explanation.
 */

export const MODEL_VERSION = "history-rules-1";

const AMOUNT_TIERS = [[1.0, 0.0], [3.0, 0.35]]; // [ratio at most, points]; above: 0.65 below 10x, 0.85 from 10x
const HIGH_POINTS = 0.65;
const CRITICAL_POINTS = 0.85;
const CRITICAL_RATIO = 10.0;
const POINTS = { first_of_kind: 0.3, new_device: 0.3, new_country: 0.3, new_payee: 0.15, night: 0.1, fast_4: 0.3, fast_6: 0.6, thin_history: 0.3 };
const THIN_HISTORY = 3;

const PURPOSE_NAMES = {
  airtime: "airtime", data: "data bundle", electricity: "electricity bill", transfer: "transfer",
  withdrawal: "cash withdrawal", payment: "payment", deposit: "deposit",
};

export const purposeOf = (row) => (row.merchant_category || "").trim().toLowerCase() || row.transaction_type || "payment";
export const purposeName = (purpose) => PURPOSE_NAMES[purpose] ?? purpose.replace(/_/g, " ");

// Round halves to the nearest EVEN number, like Python's formatting, so the sentences match the server's exactly.
const roundHalfEven = (x) => {
  const floor = Math.floor(x);
  return x - floor === 0.5 ? (floor % 2 === 0 ? floor : floor + 1) : Math.round(x);
};
const naira = (value) => `₦${roundHalfEven(value).toLocaleString("en-US")}`;
const round2 = (x) => Math.round(x * 100) / 100;
const HOUR = 3600 * 1000;
// Lagos is UTC+1 all year, so the local hour is the UTC hour plus one.
const localHour = (ms) => (new Date(ms).getUTCHours() + 1) % 24;

export function amountPoints(ratio) {
  if (ratio >= CRITICAL_RATIO) return CRITICAL_POINTS;
  for (const [limit, points] of AMOUNT_TIERS) if (ratio <= limit) return points;
  return HIGH_POINTS;
}

/** The amounts where each band starts, for a customer whose largest comparable payment is `largest`. */
export function amountBands(largest) {
  return { low_up_to: largest, medium_up_to: largest * 3, critical_from: largest * CRITICAL_RATIO };
}

/**
 * Judge the LAST row of `history` (oldest first) against the rows before it.
 * Row: { timestamp (ms), amount, transaction_type, merchant_category, device_id, country,
 *        counterparty_account, trusted? }. Payments that were not trusted (flagged) are ignored
 * when working out what is normal, but still count towards speed.
 */
export function assess(history) {
  const current = history[history.length - 1];
  const earlierAll = history.slice(0, -1);
  const earlier = earlierAll.filter((r) => r.trusted !== false);
  const reasons = {};
  let total = 0;
  const raise = (sentence, points) => {
    total += points;
    reasons[sentence] = round2(points);
  };

  const purpose = purposeOf(current);
  const kind = purposeName(purpose);
  const amount = Number(current.amount);
  const sameKind = earlier.filter((r) => purposeOf(r) === purpose).map((r) => Number(r.amount));
  const anyKind = earlier.map((r) => Number(r.amount));

  if (earlier.length < THIN_HISTORY) {
    raise(`Only ${earlier.length} earlier transaction${earlier.length !== 1 ? "s" : ""} to compare with`, POINTS.thin_history);
  }

  let largest = 0;
  let scope = "";
  if (sameKind.length) {
    largest = Math.max(...sameKind);
    scope = kind;
  } else if (anyKind.length) {
    largest = Math.max(...anyKind);
    scope = "payment of any kind";
    raise(`First time paying for ${kind}`, POINTS.first_of_kind);
  }

  if (largest > 0) {
    const ratio = amount / largest;
    const points = amountPoints(ratio);
    if (points > 0) {
      const size = ratio >= 10 ? `${roundHalfEven(ratio)} times` : ratio >= 2 ? `${(roundHalfEven(ratio * 10) / 10).toFixed(1)} times` : `${roundHalfEven((ratio - 1) * 100)}% above`;
      raise(`${naira(amount)} ${kind} is ${size} their largest ${scope} (${naira(largest)})`, points);
    } else {
      const pool = sameKind.length ? sameKind : anyKind;
      reasons[`${naira(amount)} ${kind} is within their usual ${scope} range (${naira(Math.min(...pool))} to ${naira(largest)})`] = -0.2;
    }
  }

  const devices = new Set(earlier.map((r) => r.device_id).filter(Boolean));
  if (current.device_id && devices.size && !devices.has(current.device_id)) raise("First time on this device", POINTS.new_device);
  else if (current.device_id && devices.size) reasons["Usual device"] = -0.1;

  const countries = new Set(earlier.map((r) => r.country).filter(Boolean));
  if (current.country && countries.size && !countries.has(current.country)) raise(`First time from ${current.country}`, POINTS.new_country);

  if (purpose === "transfer" && current.counterparty_account) {
    const payees = new Set(earlier.map((r) => r.counterparty_account).filter(Boolean));
    if (!payees.has(current.counterparty_account)) raise("First time paying this account", POINTS.new_payee);
    else reasons["Account they have paid before"] = -0.1;
  }

  const now = new Date(current.timestamp).getTime();
  if (localHour(now) < 6 && !earlier.some((r) => localHour(new Date(r.timestamp).getTime()) < 6)) {
    raise("Made late at night, which they never do", POINTS.night);
  }

  const recent = 1 + earlierAll.filter((r) => new Date(r.timestamp).getTime() > now - HOUR).length;
  if (recent >= 6) raise(`${recent} transactions in the last hour`, POINTS.fast_6);
  else if (recent >= 4) raise(`${recent} transactions in the last hour`, POINTS.fast_4);

  return { probability: Math.min(0.99, Math.max(0.02, round2(total))), reasons };
}
