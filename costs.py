"""Runs experiments 1-6 from measured results + pricing.json. Output: results/cost_table.{csv,md}, charts."""
import json, math, csv
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

P = json.load(open("model/pricing.json"))
B = json.load(open("results/baseline.json"))
J = json.load(open("results/batch.json"))
OD, SPOT, SP = P["ec2_on_demand_usd_per_hour"], P["ec2_spot_usd_per_hour_snapshot"], P["instance_specs"]
H = 730

# ---- ASSUMPTIONS (stated in report) ----
BASELINE_INSTANCE = "t3.xlarge"   # what an un-optimized deployment might have picked
HEADROOM = 1.3
OS_OVERHEAD_GIB = 0.4             # memory for OS/runtime not measured in the process
PEAK_DEMAND_RPS = 1000            # assumed production peak for the autoscaling scenario
TARGET_UTIL = 0.6
rows = []
def add(tech, base, opt, cur, method):
    rows.append({"technique": tech, "baseline": round(base, 4), "optimized": round(opt, 4),
                 "saving_pct": round(100 * (base - opt) / base, 1), "currency": cur, "method": method})

# ---- 1. Right-sizing: avg CPU must fit under the t3 baseline (burstable credits), peak must fit vCPU, memory must fit
def fits(i):
    s = SP[i]; base_cores = s["vcpu"] * s["baseline_pct_per_vcpu"] / 100
    return (B["peak_cpu_cores"] * HEADROOM <= s["vcpu"] and B["avg_cpu_cores"] * HEADROOM <= base_cores
            and (B["peak_mem_mib"] / 1024 + OS_OVERHEAD_GIB) * HEADROOM <= s["mem_gib"])
best = min((i for i in SP if fits(i)), key=lambda i: OD[i])
add(f"1. Right-sizing ({BASELINE_INSTANCE} -> {best})", OD[BASELINE_INSTANCE] * H, OD[best] * H, "USD/month",
    "Measured peak/avg CPU and memory x1.3 headroom; t3 baseline credit check")

# ---- 2. Pricing models on the right-sized instance (always-on)
od = OD[best] * H
pm = {"On-Demand": od, "Reserved/Savings Plan -20% (assumed)": od * .8, "Reserved/Savings Plan -30% (assumed)": od * .7,
      "Reserved/Savings Plan -40% (assumed)": od * .6, "Spot (snapshot price)": SPOT[best] * H}
for k, v in pm.items():
    if k != "On-Demand": add(f"2. Pricing model: {k}", od, v, "USD/month", f"{best}, 730 h; commitment discount is a sensitivity input, not a quoted price")

# ---- 3. Autoscaling vs fixed fleet (diurnal demand shape assumed; per-instance capacity from measured CPU/request)
cap = SP[best]["vcpu"] * SP[best]["baseline_pct_per_vcpu"] / 100 / B["cpu_seconds_per_request"] * TARGET_UTIL
demand = [PEAK_DEMAND_RPS * (0.2 + 0.8 * max(0, math.sin(math.pi * (h - 6) / 16))) if 6 <= h <= 22 else 0.2 * PEAK_DEMAND_RPS for h in range(24)]
fixed_n = math.ceil(PEAK_DEMAND_RPS / cap)
auto_hours_day = sum(max(1, math.ceil(d / cap)) for d in demand)
fixed = fixed_n * 24 * 30 * OD[best]; auto = auto_hours_day * 30 * OD[best]
add(f"3. Autoscaling ({fixed_n} fixed {best} -> scale 1..{fixed_n})", fixed, auto, "USD/month",
    f"Capacity {cap:.0f} rps/instance (measured CPU/req, baseline-credit limited); demand curve assumed")
fig, ax = plt.subplots(figsize=(7, 3.5)); ax.step(range(24), [max(1, math.ceil(d / cap)) for d in demand], where="post", label="Autoscaled")
ax.axhline(fixed_n, color="r", ls="--", label="Fixed fleet (sized for peak)"); ax.set_xlabel("Hour of day"); ax.set_ylabel("Instances"); ax.legend(); ax.set_title("Autoscaling vs fixed fleet (modeled)")
plt.tight_layout(); plt.savefig("results/autoscaling.png", dpi=150); plt.close()

# ---- 4. Serverless vs VM
L = P["lambda"]; mem_gb = 0.5
api_ms = max(1, math.ceil(B["cpu_seconds_per_request"] * 1000))
per_req = L["usd_per_million_requests"] / 1e6 + mem_gb * api_ms / 1000 * L["usd_per_gb_second"]
be = od / per_req
batch_ms = math.ceil(J["runtime_s_median"] * 1000)
per_run = L["usd_per_million_requests"] / 1e6 + mem_gb * batch_ms / 1000 * L["usd_per_gb_second"]
vm_batch = OD["t3.micro"] * H
add("4a. Serverless: nightly batch (30 runs/mo) vs always-on t3.micro", vm_batch, per_run * 30, "USD/month",
    f"Measured {J['runtime_s_median']} s/run, 512 MB; free tier ignored")
fig, ax = plt.subplots(figsize=(7, 3.5)); xs = [10 ** (k / 10) for k in range(50, 100)]
ax.loglog(xs, [x * per_req for x in xs], label="Lambda (512 MB)"); ax.axhline(od, color="r", ls="--", label=f"Always-on {best}")
ax.axvline(be, color="gray", ls=":"); ax.set_xlabel("API requests per month"); ax.set_ylabel("USD per month"); ax.legend()
ax.set_title(f"Break-even about {be/1e6:.0f}M requests/month (modeled)"); plt.tight_layout(); plt.savefig("results/breakeven.png", dpi=150); plt.close()

# ---- 5. Storage tiering: 500 GB, 10% hot / 30% infrequent / 60% cold after lifecycle rules
S = P["s3_inr_per_gb_month"]; gb = 500
add("5. Storage tiering (500 GB: 10% Standard / 30% IA / 60% Glacier Flexible)", gb * S["standard"],
    gb * (.1 * S["standard"] + .3 * S["standard_ia"] + .6 * S["glacier_flexible"]), "INR/month",
    "Per-GB rates only; retrieval, request and minimum-duration charges ignored")

# ---- 6. Scheduling dev/test: 12 h x 5 days vs 24x7
sched_h = 12 * 5 * 52 / 12
add(f"6. Scheduling dev/test {best} (12 h x 5 days)", od, sched_h * OD[best], "USD/month", "Active hours 260 vs 730")

# ---- outputs
with open("results/cost_table.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
with open("results/cost_table.md", "w") as f:
    f.write("| Technique | Baseline | Optimized | Saving % | Unit | Method |\n|---|---|---|---|---|---|\n")
    for r in rows: f.write(f"| {r['technique']} | {r['baseline']} | {r['optimized']} | {r['saving_pct']} | {r['currency']} | {r['method']} |\n")
print(open("results/cost_table.md").read())
print(f"Right-sized instance: {best}; capacity {cap:.0f} rps/instance; fixed fleet {fixed_n}; autoscaled instance-hours/day {auto_hours_day} vs {fixed_n*24}")
print(f"Lambda per API request ${per_req:.3e}; break-even {be/1e6:.1f}M req/month vs {best} ${od:.2f}/month; test load = {B['rps']*3600*730/1e6:.0f}M req/month")
