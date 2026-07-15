# Brent and WTI Contract Specifications

Closes / addresses [issue #5](https://github.com/andrewheekin/finm37000-grp-6-trading/issues/5).

Short reference for report assumptions and code (costs, session flatten, rolls, 1:1 hedge). Primary sources: [CME CL product page](https://www.cmegroup.com/markets/energy/crude-oil/light-sweet-crude.html), CME BZ / Brent Last Day Financial specs. Verify any `[VERIFY]` markers against the live CME contract specs before treating as final.

## Summary table

| Spec | CL (WTI) | BZ (Brent Last Day Financial) |
|------|----------|-------------------------------|
| Exchange / venue | NYMEX / CME Globex | NYMEX / CME Globex |
| Underlying | WTI light sweet crude | Brent crude (ICE Brent Index–linked) |
| Settlement | **Physical** (Cushing, OK) | **Financial / cash-settled** |
| Contract size | 1,000 barrels | 1,000 barrels |
| Price quotation | USD per barrel | USD per barrel |
| Min tick | $0.01 / bbl | $0.01 / bbl |
| Tick value | $10.00 / contract | $10.00 / contract |
| Globex hours (CT) | Sun–Fri 5:00 p.m.–4:00 p.m.; daily halt 4:00–5:00 p.m. | Same Globex window (align with CL for same-venue spread) `[VERIFY]` |
| Expiration cadence | Monthly | Monthly (calendar often **earlier** than CL — see rolls) |
| Databento / Globex root | `CL` | `BZ` |

## CL — WTI Light Sweet Crude Oil

- **Settlement:** Physically delivered. Holding through last trade day can create a delivery obligation at Cushing; speculative / research strategies typically roll or flatten well before expiration.
- **Size / tick:** 1,000 bbl; $0.01/bbl → $10 per tick per contract.
- **Hours:** Nearly 23-hour Globex session with a daily maintenance break (4:00–5:00 p.m. CT).
- **Last trading day (high level):** Trading typically terminates on the third business day prior to the 25th calendar day of the month preceding the delivery month. `[VERIFY exact rule for sample months]`

## BZ — Brent Crude Oil Last Day Financial

- **Settlement:** Cash-settled (financial). No physical oil delivery on CME BZ; final settlement references the ICE Brent Crude Oil Index / ICE Brent futures complex. This is the key contrast with CL.
- **Size / tick:** Same 1,000 bbl and $0.01/$10 economics as CL → a 1:1 contract spread has matched notional per barrel and matched tick value.
- **Hours:** Listed on the same Globex energy session window as CL for practical co-trading. `[VERIFY on CME BZ product sheet]`
- **Expiration:** BZ often expires earlier in the calendar than the corresponding CL month (Brent “runs earlier”). That is why same-calendar-month listed spreads and continuous-roll choices matter (see pipeline / issue #20).

## Differences that matter for our strategy

### 1. Settlement type (physical CL vs financial BZ)

Already flagged in group discussion: CME WTI is physically settled; CME Brent (BZ) is financially settled. For an **intraday, flat-at-EOD** strategy this mainly affects:

- **Delivery / expiration risk** — we must not hold CL into delivery; EOD flatten plus expiration filters (issue #11) are consistent with that.
- **Basis meaning** — the CL–BZ (or BZ–CL) spread is still an economically meaningful light-sweet differential, but the legs are not both physical delivery claims on the same venue.

### 2. Tick size → transaction costs

README baseline: start costs at **one tick + slippage per leg**.

- One tick per leg = $10 per contract.
- Round-trip on a 1:1 two-leg spread ≈ **4 ticks** of minimum exchange increment friction before slippage (enter + exit × 2 legs), i.e. **$40 / spread-lot** at one tick each way, plus slippage assumptions.
- Because CL and BZ share $10 ticks, cost modeling can stay symmetric unless we later find BZ is systematically wider.

### 3. Trading hours → EOD flatten

Both legs trade the same Globex energy session with a daily halt. “End of session” for our flatten rule should be defined explicitly in code (e.g. last bar before the 4:00 p.m. CT halt, or an earlier research cut-off). `[TODO: pick one convention in the backtester and document it here]`

### 4. Expiration / roll calendars

- CL and BZ monthly expiries are **not** aligned one-for-one.
- Pipeline uses volume-roll continuous fronts (`CL.v.0`, `BZ.v.0`) and listed same-month spreads such as `CLN6-BZQ6` (see `data_manual/data_README.md` once #4 lands).
- Spec implication: rolling statistics must not silently mix contracts across roll dates (issue #20).

### 5. Does the 1:1 spread assumption still hold?

**Yes at the contract-spec level:** same barrel multiplier (1,000) and same tick value ($10) support a static **1 contract CL vs 1 contract BZ** hedge as the README baseline. Remaining hedge-ratio work (#7) is about **price co-movement** (OLS / residual stability), not mismatched contract sizes.

**Sign convention note:** README prose often writes $S = \mathrm{BZ} - \mathrm{CL}$; the issue-#4 pipeline synthetic mid is `cl_mid - bz_mid` (CL−BZ), consistent with listed `CL*-BZ*` symbols. Specs do not prefer one sign; code and docs should pick one and stick to it.

## Consistency check vs current project assumptions

| Assumption | Spec status |
|------------|-------------|
| Products CL + BZ on CME Globex | Confirmed |
| Static 1:1 contract hedge | Supported by equal size / tick value |
| Intraday / flat at EOD | Consistent with CL physical delivery risk and shared session |
| Cost floor ≈ 1 tick/leg | Supported ($10/tick each) |
| Continuous fronts + roll handling | Required; calendars differ (BZ earlier) |

## Sources

- CME Group — WTI Crude Oil (CL) product / contract specs
- CME / NYMEX — Brent Crude Oil Last Day Financial (BZ) contract specs
- Group discussion note on physical CL vs financial BZ (issue #5 thread)

## Open follow-ups

- [ ] Paste exact CME last-trade / final-settlement wording for CL and BZ for the pilot sample months
- [ ] Confirm Globex hours line-for-line on the current BZ product sheet
- [ ] Agree code convention for “session end” (pre-halt bar) and spread sign (CL−BZ vs BZ−CL)
- [ ] Optionally mirror a short version of this page into the chartbook (`docs_src/`) after #22 merges
