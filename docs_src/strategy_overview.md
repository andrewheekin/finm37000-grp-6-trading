# Full Strategy Overview - A Walkthrough of the Architecture from Signal to Exit

This document provides a conceptual walkthrough of the intraday mean-reversion strategy used to trade the Brent–WTI spread. Its purpose is to document the full decision-making architecture of the strategy before implementation, so that each component can be understood independently and then translated cleanly into code.

At a high level, the strategy searches for temporary dislocations in the spread and enters a position only when there is sufficient evidence that the deviation is both meaningful and likely to revert over a short horizon. Rather than treating every large movement in the spread as a trading opportunity, the strategy applies a sequence of filters designed to distinguish potentially mean-reverting deviations from movements that may reflect a genuine change in the relationship between the two markets.

For each observation, the strategy evaluates the most recent rolling window of spread data and asks three questions:
1. **Is the current spread sufficiently far from its recent mean?**

    A rolling z-score measures the magnitude of the current deviation relative to the spread's recent behavior. A potential trade is considered only when this z-score crosses a configurable entry threshold.

2. **Does the spread appear mean-reverting within the current window?**

    A stationarity test is applied to a rolling window ending in the time step (which need not be identical to the rolling window used to detect deviations, although can default to it). This acts as a validity check on the signal: a large deviation is not enough on its own if the recent spread dynamics do not provide evidence of a stable, mean-reverting relationship.

3. **Is the estimated mean reversion fast enough for the strategy's intended horizon?**

    If the window passes the stationarity check, its mean-reversion half-life is estimated. The signal is accepted only when the estimated half-life falls within a configurable short-term limit, helping ensure that the expected convergence is compatible with an intraday trading strategy.

A position is entered only when all three conditions are satisfied. The direction of the trade is determined by the sign of the deviation: the strategy takes a position that benefits from the spread moving back toward its recent equilibrium.

Once a trade is open, the entry filters are replaced by a separate set of exit rules: 
- The primary exit occurs when the **z-score returns to a configurable reverted level**, indicating that the dislocation has largely closed. 
- Additional safeguards include a **maximum holding-period time stop** and a **stop-loss rule** designed to limit losses when the spread moves further away from equilibrium rather than reverting.

The architecture can therefore be summarized as:
$$ \text{Rolling Window} → \text{Z-Score Signal} → \text{Stationarity Check} → \text{Half-Life Check} → \text{Trade Entry} → \text{Exit Management} $$

All thresholds, window lengths, significance levels, holding-period limits, and risk parameters are intentionally left unspecified in this document. These values are intended to be configurable inputs within implementation so that the strategy can be tested, tuned, and compared across different parameter choices without changing its underlying logic.

The remainder of this document walks through each stage of this process in detail, beginning with the rolling window that supplies the data used by every subsequent decision.

## Rolling Window Anatomy

The rolling window is the foundation of the strategy. Every signal calculation and subsequent validity check is performed using the most recent window of spread observations, allowing the strategy to continuously evaluate the current Brent–WTI relationship relative to its recent behavior.

At each minute (t), the spread is constructed from the continuous front-month `CL.v.0` and `BZ.v.0` data from Databento. Using the bid and ask prices of the two legs, the synthetic spread bid and ask are formed, and the midpoint is calculated as:

$$
\text{Spread Mid}_t
=
\frac{\text{Spread Bid}_t + \text{Spread Ask}_t}{2}
$$

The rolling window at time (t) contains the most recent (n) midpoint observations:

$$
W_t = \{S_{t-n+1}, \ldots, S_t\}
$$

where (n) is a configurable window length.
The windows are overlapping rather than divided into fixed blocks. In live trading, every new minute causes the window to roll forward by one observation. The strategy then restarts its decision process from the top using the newly formed window:
$$ \text{New observation} → \text{Update spread} → \text{Roll window} → \text{Run signal checks} $$

**Window Validity**

A rolling window should only be used if:
- it contains the full required number of one-minute observations;
- the observations are continuous in time;
- it does not cross a change in the underlying contract represented by either CL.v.0 or BZ.v.0.

The final condition handles futures rolls. Because the continuous symbols can switch from one underlying futures contract to another, a window that spans an instrument transition may contain a mechanical price discontinuity caused by the roll rather than a genuine movement in the Brent–WTI relationship.

The implementation should therefore use the instrument identifiers in the data to determine whether either leg changes contract within the current window. If a transition occurs, that window is discarded. Once enough observations from the new contracts have accumulated to form a complete post-roll window, signal evaluation resumes normally.

## Test 1: Z-Score

Once a rolling window has passed the structural validity checks, the strategy's first signal check is the current spread z-score.

The z-score measures how far the most recent spread midpoint is from the mean of its rolling window, expressed in units of the window's standard deviation:

$$
z_t = \frac{S_t - \mu_t}{\sigma_t}
$$

where:
- $S_t$ is the current synthetic spread midpoint;
- $\mu_t$ is the mean spread midpoint within the current rolling window; 
- $\sigma_t$ is the standard deviation of the spread midpoint within that window.

Because both the mean and standard deviation are recalculated from the current rolling window, the z-score measures the current spread relative to its recent local behavior, rather than against a fixed long-run level.

A potential trade is generated when the **absolute value of the current z-score exceeds a configurable entry threshold**:

$$
|z_t| \geq z_{\text{entry}}
$$

The threshold $z_{\text{entry}}$ should remain a configurable strategy parameter rather than being hard-coded.

The sign of the z-score determines the direction of the potential trade:
- Positive z-score: The spread is above its recent mean, so the candidate trade is positioned for the spread to decrease.
- Negative z-score: The spread is below its recent mean, so the candidate trade is positioned for the spread to increase.

Crossing the entry threshold does not immediately cause the strategy to enter a position.
A large z-score only establishes that the current spread is unusually far from its recent mean. It does not establish that the spread is actually mean-reverting. A large deviation could instead reflect a trend, structural change, or other shift in the relationship between Brent and WTI.
The z-score therefore acts as the first filter in the strategy architecture.

## Test 2: Stationarity

If the current z-score crosses the entry threshold, the strategy next evaluates whether the spread within the current rolling window exhibits sufficiently stationary behavior. 

Rather than hard-coding a particular stationarity test into the strategy, the strategy in practice can use multiple tests that can be independently enabled or disabled. This is for the purpose of having flexibility in both backtesting and live usage to see which combination of tests prove to be the most profitable from a P&L perspective; specifically, the implementation would allow the user to toggle which tests to use for a run of the strategy, for example:

- use_adf = `True` / `False`
- use_kpss = `True` / `False`
- Additional tests can be added in the same way if needed

The statistical parameters associated with each test, including significance levels and time window, should also remain configurable rather than being hard-coded. The implementation then combines the results of the enabled tests according to the chosen stationarity rule. For example, the strategy may require all enabled tests to agree that the window is sufficiently stationary before allowing the signal to continue. This decision rule should itself be implemented flexibly so that alternative combinations can be evaluated during backtesting if desired.

The stationarity stage ultimately produces a simple pass/fail decision:
- Stationarity criteria fail → Reject signal
- Stationarity criteria pass → Continue to half-life estimation

If the window fails the configured stationarity criteria, no position is entered. The strategy waits for the next one-minute observation, rolls the window forward, and begins the signal-generation process again from the z-score check. If the window passes, the signal proceeds to the final validation stage: estimating whether the window's mean-reversion half-life is sufficiently short for the strategy's intended intraday horizon.

## Test 3: Half-Life Estimation

The mean-reversion half-life represents the estimated amount of time required for a deviation from equilibrium to shrink by one-half. For an intraday strategy, this provides a practical measure of whether the spread is expected to revert quickly enough for the candidate trade to be worthwhile. A spread may appear stationary while still reverting too slowly for the intended holding horizon. The half-life check therefore acts as the final validation step before trade entry.

For the current rolling window, define the one-period change in the spread as:
$$
\Delta S_t = S_t - S_{t-1}
$$
The strategy estimates the relationship:
$$
\Delta S_t = \alpha + \beta S_{t-1} + \varepsilon_t
$$
where:

- $S_{t-1}$ is the lagged spread midpoint,
- $\Delta S_t$ is the subsequent one-minute change in the spread,
- $\alpha$ is an intercept,
- $\beta$ measures the tendency of the spread to move back toward equilibrium,
- $\varepsilon_t$ is the residual term.

For mean reversion to be present, the estimated coefficient (\beta) should be negative. This means that when the spread is relatively high, its subsequent expected change is downward, and when the spread is relatively low, its subsequent expected change is upward.

The estimated half-life is then:
$$
h = \frac{\ln(2)}{-\beta}
$$
Because the strategy uses one-minute observations, $h$ is interpreted in minutes.

The estimated half-life is compared against a configurable maximum acceptable value:
$$
0 < h \leq h_{\text{max}}
$$
where $h_{\text{max}}$ represents the longest expected reversion period that the strategy is willing to accept.

If the estimated half-life exceeds this limit, the candidate signal is rejected. Although the spread may exhibit mean-reverting behavior, the expected convergence would be too slow for the strategy's intended short-term horizon, making the spread increasingly vulnerable to regime changes and less likely to cleanly mean revert. 

The signal will also be rejected when the half-life cannot be interpreted meaningfully. This includes cases where:
- the estimated (\beta) is zero or positive;
- the resulting half-life is nonpositive;
- the estimate is missing, infinite, or otherwise numerically invalid.

If the estimate is valid and falls within the configured limit, the candidate signal passes the final entry check.

This check will also come with a Boolean toggle when running the strategy, so that backtesting will allow the user to explore cases in which half-life isn't used as a filter and compare results.

The half-life stage completes the sequence of entry checks:
$$ \text{Stationarity Criteria Met → Estimate Half-Life → Half-Life Acceptable?} $$

No → reject the signal and restart on the next observation.

Yes → approve the signal for trade entry.

Together, these conditions require the spread to be meaningfully displaced, statistically consistent with mean reversion, and expected to revert within an acceptable intraday timeframe.

## Exit Methodology

Once a position has been entered, the strategy stops evaluating the entry filters for that trade and begins monitoring a separate set of exit conditions.
The purpose of the exit framework is to close the position when:
- the expected mean reversion has occurred;
- the trade has remained open longer than intended;
- the spread continues moving against the position;
- the strategy reaches the end of its permitted trading session.

Each exit rule should be configurable so that alternative specifications can be compared during backtesting.

### Z-Score Reversion Exit

The primary exit occurs when the spread returns sufficiently close to its recent equilibrium. Because the trade was entered after the z-score crossed an extreme entry threshold, the position is expected to profit as the z-score moves back toward zero. The strategy should therefore define a configurable exit level:
$$
z_{\text{exit}}
$$

The exit threshold will generally be closer to zero than the entry threshold. For a trade entered when the spread was above its rolling mean, the position should be closed once the z-score falls to the configured reverted level:
$$
z_t \leq z_{\text{exit}}
$$

For a trade entered when the spread was below its rolling mean, the position should be closed once the z-score rises to the corresponding lower-side exit level:
$$
z_t \geq -z_{\text{exit}}
$$

Equivalently, a symmetric specification may close the trade when:
$$
|z_t| \leq z_{\text{exit}}
$$

This does not require the z-score to return exactly to zero. Requiring complete convergence may cause the strategy to remain in a trade after most of the expected reversion has already occurred.

The exit threshold should remain configurable so backtesting can evaluate the trade-off between:
- exiting earlier and realizing gains more quickly;
- waiting for greater convergence and potentially capturing more of the spread movement.

### Time Stop Exit

A time stop closes a position once it has been held for longer than a configurable maximum duration:
$$
T_{\text{held}} \geq T_{\text{max}}
$$

where:
- $T_{\text{held}}$ is the number of minutes elapsed since entry;
- $T_{\text{max}}$ is the maximum permitted holding period.

Because the strategy is designed around short-term intraday mean reversion, if the spread has not reverted within the expected timeframe, the original trading thesis may no longer be valid.
The time stop also prevents capital from remaining tied up in stale positions and limits exposure to changing market conditions.

The maximum holding period should be configurable and may be informed by the half-life estimates observed during strategy development and backtesting.

### Stop-Loss Exit

The stop-loss rule closes the position when the loss reaches a configurable limit. A stop loss may be defined using realized and unrealized trade P&L:
$$
\text{PnL}_t \leq -L_{\text{max}}
$$

where $L_{\text{max}}$ is the maximum acceptable loss per trade.

Alternatively, the stop may be expressed in terms of additional spread or z-score movement against the position. The implementation should allow the chosen stop-loss specification and its associated limit to remain configurable.
The purpose of this rule is to protect the strategy when the spread does not revert as expected and instead continues moving away from the entry level. This may occur because of a structural market move, a breakdown in the recent relationship between Brent and WTI, or an unusually large short-term shock.
A stop-loss exit should override the expectation that the spread may eventually revert. Once the configured loss limit is reached, the position should be closed rather than held indefinitely.

### End-of-Session Exit

Because the strategy is intraday, all open positions should be closed before the end of the configured trading interval.
If a position remains open when the strategy reaches its configured session-ending time, it should be exited regardless of its current z-score, holding period, or P&L.

This prevents overnight exposure and ensures that the strategy begins each new trading session without an existing position.
The session-ending time should be configurable alongside the daily start and end times used to construct valid rolling windows.

Each exit mechanism should be independently enabled or disabled using Boolean parameters, for example:
- use_zscore_exit = `True` / `False`
- use_time_stop = `True` / `False`
- use_stop_loss = `True` / `False`
- use_session_exit = `True` / `False`

The associated thresholds and limits should also remain configurable.

This design allows the team to compare different exit specifications without rewriting the core strategy. For example, backtesting can determine whether the time stop improves performance, whether a stop loss is too restrictive, or whether a partial z-score reversion is a better exit target than a return to zero.

The exit process can therefore be summarized as:
$$ \text{Open Position → Update Position Each Minute → Evaluate Exit Conditions → Close Position When Any Enabled Rule Is Triggered} $$
Once the trade is closed, the strategy returns to its normal signal-generation process and begins searching for the next valid entry opportunity.
