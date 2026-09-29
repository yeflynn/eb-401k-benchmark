# 401(k) Peer Benchmark

Internal administrator tool. Compares featured employer 401(k) plans against a
market universe built from DOL Form 5500 filings (plan year 2024).

Private use only — not linked from any public site.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Data

`data/peer_401k_2024.csv` — 26,867 rows:
- 26,863-plan market universe: 401(k) plans (characteristic code 2J), plan year
  2024, 200–2,000 active participants, positive employee contributions.
- 4 featured plans flagged in the `featured` column (`tmna`, `tri`, `tcna`, `woven`).

Source files (not committed): DOL Form 5500 FOIA datasets,
`F_5500_2024_Latest` + `F_SCH_H_2024_Latest`.
