# Cost Optimization Techniques in Cloud Computing (PBL)

A zero-spend, measurement-driven comparison of six cloud cost optimization techniques.
Utilization and runtime are **measured** on a local workload; all dollar figures are **modeled**
from published AWS list prices (Mumbai, ap-south-1).

## Techniques evaluated
1. Right-sizing
2. Pricing models (On-Demand, Reserved/Savings Plan range, Spot)
3. Autoscaling vs fixed fleet
4. Serverless vs always-on compute (break-even)
5. Storage tiering
6. Scheduling dev/test environments

## Requirements
Python 3.10+ and `pip install -r requirements.txt`

## Run (from the repository root)
```bash
python3 workload/load.py     # ~50 s: starts the API, runs a fixed load, measures CPU/memory -> results/baseline.json
python3 workload/batch.py    # nightly batch job runtime/memory -> results/batch.json
python3 model/costs.py       # runs the six experiments -> results/cost_table.md/.csv + charts
```
The API listens on port 8765. If it is busy, change the port in `workload/server.py` and `workload/load.py`.

## Measured vs modeled
- Measured: `results/baseline.json`, `results/batch.json`
- Modeled: everything in `results/cost_table.*` (prices in `model/pricing.json`)

## Assumptions (stated in `model/costs.py`)
Baseline instance t3.xlarge, 1.3x headroom, 0.4 GiB OS overhead, assumed peak of 1,000 requests/s
and a daily demand curve for autoscaling, Reserved/Savings Plan discount range of 20-40%.

## Limitations
- Measurements come from a local machine, not cloud instances.
- Prices were taken from third-party listings (see `model/pricing.json`); verify against the AWS pricing pages.
- The workload is small and synthetic, so results show direction and relative savings, not guaranteed bills.
