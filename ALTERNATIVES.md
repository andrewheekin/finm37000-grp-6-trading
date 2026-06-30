# Trading Strategy Alternatives
FINM 37000 Summer '26 — **Group 6**
**Team:** Andrew Heekin, Michael Dowling, Sam Zhang, Bobby Kodem

This document captures the the trading strategy candidates from our team discussions. Our goal here is to document what we discussed as a group before we locked the final strategy in `README.md`.

---

## Strategy titles at a glance

| Title | Author | Type |
|-------|--------|------|
| **The Brent–WTI Spread Reversion** | Michael Dowling | Primary candidate — intra-commodity mean reversion |
| **The Macro-Gated Brent–WTI** | Sam Zhang | Overlay on Michael's strategy — rates/VIX filters |
| **The Oil–Rates Cross-Asset Reversion** | Andrew Heekin | Alternative — CL vs SR3 as primary trade |
| **Mental model of the core strategy** | Bobby Kodem | Discussion — sanity check on Michael's framework |

---

## Option A — The Brent–WTI Spread Reversion

**Author:** Michael Dowling (`mcdowling`)

**Summary:** Intraday mean-reversion on the Brent–WTI crude oil spread. Relative-value / statistical-arbitrage on spread.

**Methodology (high level):**
- **Spread:** Baseline static 1:1 spread; optional hedge-ratio refinement (TLS / Kalman).
- **Signal:** Z-score of spread vs trailing mean/σ; entry/exit bands.
- **Validation:** Stationarity / cointegration tests (ADF, KPSS, Engle–Granger); half-life via AR(1) / OU process.
- **Risk:** Time-stop at multiple of half-life; end-of-session flatten; vol-scaled sizing.
- **Data:** Databento CME Globex (`GLBX`) — BZ, CL; resolution TBD.

---

## Option A+ — The Macro-Gated Brent–WTI Strategy

**Author:** Sam Zhang (`SamZhang24z`)

**Summary:** Keep Michael's Brent–WTI core, but add macro signals to control when and how aggressively to trade.

### Macro filter & VIX-adjusted entry

> Instead of pairing WTI and SR3, we could use Interest rate futures or VIX as an additional macro signal for the Brent-WTI strategy.
>
> - Use the interest rate futures as a regime filter(avoid trades during large macro-driven rate moves)
> - Adjust the z-score entry threshold based on the VIX

### Exit threshold

> Let's set a specific exit threshold. Here are some ideas I have.
> Z-score: Exit when the spread returns close to its mean (e.g., (|z| < 0.5)).
> Velocity: Exit if the z-score stops reverting quickly (low rate of change).
> Acceleration: Exit if the mean-reversion momentum is slowing significantly.
> Half-life: Close the position after a multiple of the estimated half-life if reversion hasn't occurred.
> PnL target: Exit after reaching a predefined profit target.
> Volatility: Exit when spread volatility becomes unusually high, indicating a possible regime change.
> Stationarity: Exit if the rolling stationarity/cointegration tests fail while the trade is open.
> Probability of reversion: Use a model to estimate the likelihood of further mean reversion and exit when that probability falls below a threshold.

---

## Option B — The Oil–Rates Cross-Asset Reversion Strategy

**Author:** Andrew Heekin (`andrewheekin`)

**Summary:** Cross-asset mean-reversion on WTI and front-end rates.

### Andrew's comment

> One final strategy alternative (to show we've considered options 🙂) - Instead of treating rates as a side leg on Brent-WTI, we could build a standalone cross-asset mean-reversion strategy on WTI (CL) and front-end rates (SR3):
>
> - Trade the CL–SR3 spread directly when the oil–rates relationship stretches vs a rolling fair value (z-score entry/exit, same statistical framework as Michael's strategy
> - Use Brent–WTI as a signal and only take CL–SR3 trades when the crude isn't in a geographic dislocation (Brent–WTI stable), to avoid double-counting an energy shock.

---

## Mental model of the core strategy

**Author:** Bobby Kodem (`bkodem2025`)

**Note:** Bobby's comment below is a write-up to test his understanding of Michael's proposed methodolog.

### Bobby's comment

> in order to capture non 1:1 but still linear and proportionate movements between BZ and CL, rather than using a simple 1:1 spread where we subtract one from the other, we pick one to be the dependent leg and derive a relationship where its relative value can be estimated based on the independent leg. then, the strategy will use this relationship to generate signals; if the fair value of the dependent leg estimated by the relationship is meaningfully different from the actual value (i.e., the residual (the spread) between the actual and fair is above some threshold), then that is a signal to trade)
>
> the actual signal to trade is generated using z-score. we choose some time window, say the last few days or something, and within that window find the mean spread and volatility (standard deviation). then, at every interval, we compute the z-score for that interval by subtracting the mean spread from the current spread, and then dividing that value by the volatility. z-score, thus, represents the number of standard deviations away from the average a data point is. if the z-score is above a certain threshold, then we know that the spread is meaningfully large enough to bet on the spread closing (mean reversion), and we place a trade accordingly
>
> however, this whole theoretical framework would only work in practice if we know that the spread moves with stationarity, meaning the spread usually fluctuates around some level. if the spread randomly evolves over time, then it is not stationary, and thus the strategy wouldn't work bc permanent shifts in the spread pattern would be misinterpreted as an "unusually large spread" signal. Thus, stationarity tests must be run to ensure that the backbone of the framework is strong enough to reliably execute the strategy
>
> the way this will work in practice is as follows: whenever a trade signal is given, the test will use a rolling window and test whether the spreads in that window appear meaningfully stationary; the strategy will only move forward should the tests pass. this ensures that the spread has recently been behaving in a mean-reverting way sufficiently enough for us to reliably bet that it will continue to
>
> we manage risk through a variety of approaches:
>
> - we want to avoid overnight positions, so we stay within a certain multiple of reversion half-life and close positions before end of session.
> - we scale size of the trade based on volatility; the higher the recent volatility, the smaller we trade, and the smaller the recent volatility, the larger we trade (ex. if our current spread is 1 and standard deviation is 0.2, that's a big and reliable deviation, but if sd is 1.5, then the current spread of 1 carries much more risk).
> - we place a risk stop to protect against a broken stationarity assumption: if a spread is meaningfully large but also suspiciously too large, we don't pursue the trade
