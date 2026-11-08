"""Nightly report job: aggregate 500k orders. Records wall time and peak memory -> results/batch.json."""
import sqlite3, time, resource, json, os
os.makedirs("results", exist_ok=True)
c = sqlite3.connect(":memory:")
c.execute("CREATE TABLE orders(id INTEGER PRIMARY KEY, item TEXT, qty INT)")
c.executemany("INSERT INTO orders(item,qty) VALUES(?,?)", ((f"sku{i%50}", i % 5 + 1) for i in range(500000)))
runs = []
for _ in range(5):
    t = time.perf_counter()
    rows = c.execute("SELECT item, sum(qty), count(*) FROM orders GROUP BY item").fetchall()
    runs.append(time.perf_counter() - t)
out = {"rows_scanned": 500000, "runtime_s_median": round(sorted(runs)[2], 4),
       "runtime_s_all": [round(x, 4) for x in runs],
       "peak_mem_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)}
json.dump(out, open("results/batch.json", "w"), indent=2); print(out)
