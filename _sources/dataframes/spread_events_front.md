## Description

Raw cleaned top-of-book event series for the front exchange-listed
Brent-WTI spread instrument (`CLN6-BZQ6`) over the pilot week — every MBP-1
book event as it occurred, no gridding or forward-filling. This book *is*
the tradeable Brent-WTI spread, so its event sequence is stored as-is;
downstream code decides how to sample it.

```python
from clean_mbp1 import load_spread_events
events = load_spread_events()  # front spread by default
```

Event series for the other two listed spreads (`CLQ6-BZQ6`, `CLU6-BZU6`)
exist under the same naming scheme:
`load_spread_events("CLQ6-BZQ6")`.

## Data Dictionary

Index: `ts_recv` — `datetime64[ns, UTC]`, one row per book event.

- **`instrument_id`**: `uint32` — the spread instrument's id
- **`action`**: `str` — MBP-1 action code (`A` add, `C` cancel, `M` modify, `T` trade, ...)
- **`side`**: `str` — side of the event (`B` bid, `A` ask, `N` none)
- **`price`**: `float64` — event price ($/bbl; spread prices are typically negative, Brent over WTI)
- **`size`**: `float64` — event size (contracts)
- **`bid_px_00`**, **`ask_px_00`**: `float64` — best bid/ask after the event
- **`bid_sz_00`**, **`ask_sz_00`**: `float64` — size at best bid/ask after the event
- **`mid`**: `float64` — (bid + ask) / 2
- **`is_crossed`**: `bool` — bid ≥ ask (flagged, not dropped)
