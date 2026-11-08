"""Fixed load profile (keep IDENTICAL across runs): USERS users, 80% GET / 20% POST, think time 50-150 ms.
Starts the server, drives load, samples server CPU/memory with psutil, writes results/baseline.json."""
import subprocess, threading, time, json, random, statistics, urllib.request, psutil, sys, os

USERS, DURATION, SEED = 20, 45, 42
random.seed(SEED)
os.makedirs("results", exist_ok=True)
srv = subprocess.Popen([sys.executable, "workload/server.py"])
time.sleep(2)
p = psutil.Process(srv.pid)
lat, errs, stop = [], [0], time.time() + DURATION + 0

def user():
    r = random.Random()
    while time.time() < stop:
        t = time.time()
        try:
            if r.random() < 0.8:
                urllib.request.urlopen("http://127.0.0.1:8765/orders").read()
            else:
                body = json.dumps({"item": f"sku{r.randint(1,50)}", "qty": r.randint(1,5)}).encode()
                req = urllib.request.Request("http://127.0.0.1:8765/orders", data=body, method="POST")
                urllib.request.urlopen(req).read()
            lat.append(time.time() - t)
        except Exception:
            errs[0] += 1
        time.sleep(r.uniform(0.05, 0.15))

samples = []
def sampler():
    while time.time() < stop:
        samples.append((p.cpu_percent(interval=1.0), p.memory_info().rss / 2**20))

cpu0 = sum(p.cpu_times()[:2])
th = [threading.Thread(target=user) for _ in range(USERS)] + [threading.Thread(target=sampler)]
t0 = time.time(); [t.start() for t in th]; [t.join() for t in th]; wall = time.time() - t0
cpu_s = sum(p.cpu_times()[:2]) - cpu0
srv.terminate()

lat.sort(); n = len(lat)
out = {
  "users": USERS, "duration_s": round(wall, 1), "requests": n, "errors": errs[0],
  "rps": round(n / wall, 1),
  "p50_ms": round(1000 * lat[n // 2], 1), "p95_ms": round(1000 * lat[int(n * .95)], 1),
  "peak_cpu_cores": round(max(s[0] for s in samples) / 100, 2),
  "avg_cpu_cores": round(statistics.mean(s[0] for s in samples) / 100, 2),
  "peak_mem_mib": round(max(s[1] for s in samples), 1),
  "server_cpu_seconds": round(cpu_s, 2),
  "cpu_seconds_per_request": round(cpu_s / n, 5),
}
json.dump(out, open("results/baseline.json", "w"), indent=2)
print(json.dumps(out, indent=2))
