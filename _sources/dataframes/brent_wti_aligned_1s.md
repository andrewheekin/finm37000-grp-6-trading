## Description

Identical layout to the Brent-WTI Aligned (1-minute) dataset, on a
1-second grid — ~430,000 rows over the pilot week. Intended for signal
work and microstructure checks where 1-minute buckets are too coarse.

```python
from clean_mbp1 import load_aligned
aligned = load_aligned("1s")
```

## Data Dictionary

See the Brent-WTI Aligned (1-minute) page — columns, conventions, and the
missing-data rules are identical; only the bucket size differs. The
600-second forward-fill limit spans 600 buckets on this grid (vs 10 on the
1-minute grid).
