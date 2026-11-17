# The three customers: history and what will be flagged

Everything below is produced by the same code the app runs, so the results are exact. They are true **right after a fresh start** (after a deploy or after pressing *Reset demo data* on the Customers page). The app only learns from Low-risk or analyst-cleared payments, so a flagged payment never changes the numbers, but a Medium one you clear as a false alarm will.

**Colours.** Low = green. Medium = yellow (goes through, but unusual). High and Critical = red (flagged, held for review, alert pops up). Medium starts at 30%, High at 60%, Critical at 85%.

**How the amount is judged.** Compare with the *largest* payment of the same kind (airtime, data, bill, transfer, cash withdrawal) the customer has made before. Up to that: normal. Above it, up to 3 times: Medium. 3 to 10 times: High. 10 times or more: Critical. If they have never made that kind of payment, it is Medium on its own and compared with their biggest payment of any kind.

**Other signals add to the score:** device they have never used +30%, country they have never paid from +30%, a kind of payment never made +30%, a new account on a transfer +15%, late at night when they never are +10%, 4 payments in an hour +30% (6 or more +60%).


---

## Chidi Okafor (chidi@example.com)

Salaried worker. Buys airtime and data often, pays electricity, sends money to his mum. Usual device: `chidi-iphone-13`, always from Nigeria (Lagos).

### Payment history (what the app has on file)

| Days ago | Time | What for | Amount | Paid to |
|---|---|---|---|---|
| 44 | 09:00 | Airtime | ₦1,000 | - |
| 41 | 18:00 | Transfer | ₦25,000 | Mum (0123456789) |
| 38 | 12:00 | Electricity bill | ₦15,000 | - |
| 35 | 10:00 | Data bundle | ₦3,500 | - |
| 33 | 19:00 | Airtime | ₦500 | - |
| 30 | 13:00 | Transfer | ₦30,000 | Mum (0123456789) |
| 27 | 09:00 | Airtime | ₦2,000 | - |
| 24 | 16:00 | Electricity bill | ₦12,000 | - |
| 21 | 11:00 | Data bundle | ₦3,500 | - |
| 18 | 20:00 | Airtime | ₦1,000 | - |
| 15 | 14:00 | Transfer | ₦5,000 | Friend (Emeka) (0456789012) |
| 12 | 10:00 | Airtime | ₦1,000 | - |
| 9 | 17:00 | Electricity bill | ₦18,000 | - |
| 7 | 12:00 | Data bundle | ₦3,500 | - |
| 5 | 15:00 | Transfer | ₦20,000 | Mum (0123456789) |
| 3 | 09:00 | Airtime | ₦500 | - |
| 1 | 18:00 | Airtime | ₦2,000 | - |

### What is normal, and where each level starts

| Kind of payment | Usual range | Low (normal) | Medium | High (flagged) | Critical (flagged) |
|---|---|---|---|---|---|
| Airtime | ₦500 to ₦2,000 | up to ₦2,000 | up to ₦6,000 | up to ₦19,999 | ₦20,000 and more |
| Data bundle | ₦3,500 to ₦3,500 | up to ₦3,500 | up to ₦10,500 | up to ₦34,999 | ₦35,000 and more |
| Electricity bill | ₦12,000 to ₦18,000 | up to ₦18,000 | up to ₦54,000 | up to ₦179,999 | ₦180,000 and more |
| Transfer | ₦5,000 to ₦30,000 | up to ₦30,000 | up to ₦90,000 | up to ₦299,999 | ₦300,000 and more |
| Cash withdrawal | never made | - | first one is Medium | - | a large one is flagged |

### Amounts to try on stage

| What for | Amount | Result | Why / note |
|---|---|---|---|
| Airtime | ₦1,500 | **LOW (green)** 2% | normal top-up |
| Airtime | ₦2,000 | **LOW (green)** 2% | his biggest ever |
| Airtime | ₦2,100 | **MEDIUM (yellow)** 35% | just above his biggest |
| Airtime | ₦5,000 | **MEDIUM (yellow)** 35% |  |
| Airtime | ₦10,000 | **HIGH (red, flagged)** 65% |  |
| Airtime | ₦20,000 | **CRITICAL (dark red, flagged)** 85% | 10 times his biggest |
| Airtime | ₦50,000 | **CRITICAL (dark red, flagged)** 85% | the headline demo |
| Data bundle | ₦3,500 | **LOW (green)** 2% | his usual bundle |
| Data bundle | ₦20,000 | **HIGH (red, flagged)** 65% |  |
| Electricity bill | ₦16,000 | **LOW (green)** 2% |  |
| Transfer | ₦30,000 | **LOW (green)** 2% | to Mum |
| Transfer | ₦100,000 | **HIGH (red, flagged)** 80% | to a NEW account; send to *A new account* |
| Transfer | ₦300,000 | **CRITICAL (dark red, flagged)** 99% | to a NEW account; send to *A new account* |
| Airtime | ₦1,000 | **MEDIUM (yellow)** 30% | normal amount, unknown device; tick *Use a new, unknown device* |
| Airtime | ₦1,000 | **HIGH (red, flagged)** 60% | unknown device AND from Russia; tick *Use a new, unknown device*; tick *Pay from abroad* |

---

## Ngozi Eze (ngozi@example.com)

Small-business owner. Large transfers to two suppliers, bills, cash withdrawals. Usual device: `ngozi-samsung-a54`, always from Nigeria (Lagos).

### Payment history (what the app has on file)

| Days ago | Time | What for | Amount | Paid to |
|---|---|---|---|---|
| 43 | 10:00 | Transfer | ₦150,000 | Supplier A (0234567890) |
| 40 | 14:00 | Electricity bill | ₦35,000 | - |
| 38 | 09:00 | Airtime | ₦5,000 | - |
| 36 | 11:00 | Transfer | ₦90,000 | Supplier B (0345678901) |
| 33 | 13:00 | Cash withdrawal | ₦50,000 | - |
| 31 | 16:00 | Transfer | ₦200,000 | Supplier A (0234567890) |
| 28 | 10:00 | Data bundle | ₦10,000 | - |
| 26 | 15:00 | Electricity bill | ₦40,000 | - |
| 23 | 12:00 | Transfer | ₦180,000 | Supplier A (0234567890) |
| 20 | 09:00 | Cash withdrawal | ₦40,000 | - |
| 18 | 17:00 | Airtime | ₦10,000 | - |
| 15 | 11:00 | Transfer | ₦120,000 | Supplier B (0345678901) |
| 12 | 14:00 | Electricity bill | ₦38,000 | - |
| 10 | 10:00 | Cash withdrawal | ₦60,000 | - |
| 8 | 12:00 | Transfer | ₦250,000 | Supplier A (0234567890) |
| 5 | 09:00 | Airtime | ₦5,000 | - |
| 2 | 16:00 | Data bundle | ₦10,000 | - |

### What is normal, and where each level starts

| Kind of payment | Usual range | Low (normal) | Medium | High (flagged) | Critical (flagged) |
|---|---|---|---|---|---|
| Airtime | ₦5,000 to ₦10,000 | up to ₦10,000 | up to ₦30,000 | up to ₦99,999 | ₦100,000 and more |
| Data bundle | ₦10,000 to ₦10,000 | up to ₦10,000 | up to ₦30,000 | up to ₦99,999 | ₦100,000 and more |
| Electricity bill | ₦35,000 to ₦40,000 | up to ₦40,000 | up to ₦120,000 | up to ₦399,999 | ₦400,000 and more |
| Transfer | ₦90,000 to ₦250,000 | up to ₦250,000 | up to ₦750,000 | up to ₦2,499,999 | ₦2,500,000 and more |
| Cash withdrawal | ₦40,000 to ₦60,000 | up to ₦60,000 | up to ₦180,000 | up to ₦599,999 | ₦600,000 and more |

### Amounts to try on stage

| What for | Amount | Result | Why / note |
|---|---|---|---|
| Transfer | ₦200,000 | **LOW (green)** 2% | to Supplier A |
| Transfer | ₦250,000 | **LOW (green)** 2% | her biggest ever |
| Transfer | ₦400,000 | **MEDIUM (yellow)** 35% | to Supplier A |
| Transfer | ₦1,000,000 | **HIGH (red, flagged)** 80% | to a NEW account; send to *A new account* |
| Transfer | ₦2,500,000 | **CRITICAL (dark red, flagged)** 85% | 10 times her biggest |
| Airtime | ₦8,000 | **LOW (green)** 2% |  |
| Airtime | ₦50,000 | **HIGH (red, flagged)** 65% | 5 times her biggest airtime |
| Electricity bill | ₦40,000 | **LOW (green)** 2% |  |
| Cash withdrawal | ₦50,000 | **LOW (green)** 2% |  |
| Cash withdrawal | ₦100,000 | **MEDIUM (yellow)** 35% |  |
| Cash withdrawal | ₦600,000 | **CRITICAL (dark red, flagged)** 85% | 10 times her biggest |

---

## Tunde Bello (tunde@example.com)

Student on a small budget. Small airtime and data top-ups, small transfers. Has never paid a bill. Usual device: `tunde-tecno-spark`, always from Nigeria (Lagos).

### Payment history (what the app has on file)

| Days ago | Time | What for | Amount | Paid to |
|---|---|---|---|---|
| 36 | 10:00 | Airtime | ₦200 | - |
| 33 | 15:00 | Airtime | ₦300 | - |
| 30 | 12:00 | Data bundle | ₦1,000 | - |
| 27 | 18:00 | Transfer | ₦5,000 | Parents (0567890123) |
| 24 | 09:00 | Airtime | ₦500 | - |
| 21 | 14:00 | Airtime | ₦200 | - |
| 18 | 11:00 | Data bundle | ₦1,500 | - |
| 15 | 16:00 | Transfer | ₦3,000 | Friend (Seun) (0678901234) |
| 12 | 10:00 | Airtime | ₦300 | - |
| 9 | 13:00 | Cash withdrawal | ₦5,000 | - |
| 6 | 19:00 | Data bundle | ₦1,000 | - |
| 4 | 12:00 | Airtime | ₦500 | - |
| 2 | 15:00 | Transfer | ₦10,000 | Parents (0567890123) |

### What is normal, and where each level starts

| Kind of payment | Usual range | Low (normal) | Medium | High (flagged) | Critical (flagged) |
|---|---|---|---|---|---|
| Airtime | ₦200 to ₦500 | up to ₦500 | up to ₦1,500 | up to ₦4,999 | ₦5,000 and more |
| Data bundle | ₦1,000 to ₦1,500 | up to ₦1,500 | up to ₦4,500 | up to ₦14,999 | ₦15,000 and more |
| Electricity bill | never made | - | first one is Medium | - | a large one is flagged |
| Transfer | ₦3,000 to ₦10,000 | up to ₦10,000 | up to ₦30,000 | up to ₦99,999 | ₦100,000 and more |
| Cash withdrawal | ₦5,000 to ₦5,000 | up to ₦5,000 | up to ₦15,000 | up to ₦49,999 | ₦50,000 and more |

### Amounts to try on stage

| What for | Amount | Result | Why / note |
|---|---|---|---|
| Airtime | ₦500 | **LOW (green)** 2% | his biggest ever |
| Airtime | ₦750 | **MEDIUM (yellow)** 35% |  |
| Airtime | ₦1,000 | **MEDIUM (yellow)** 35% |  |
| Airtime | ₦5,000 | **CRITICAL (dark red, flagged)** 85% | 10 times his biggest |
| Airtime | ₦50,000 | **CRITICAL (dark red, flagged)** 85% | the headline demo |
| Data bundle | ₦1,500 | **LOW (green)** 2% |  |
| Data bundle | ₦5,000 | **HIGH (red, flagged)** 65% |  |
| Electricity bill | ₦5,000 | **MEDIUM (yellow)** 30% | he has NEVER paid a bill |
| Electricity bill | ₦50,000 | **CRITICAL (dark red, flagged)** 95% | never paid a bill, and huge |
| Transfer | ₦10,000 | **LOW (green)** 2% | to Parents |
| Cash withdrawal | ₦5,000 | **LOW (green)** 2% |  |
| Cash withdrawal | ₦20,000 | **HIGH (red, flagged)** 65% |  |
