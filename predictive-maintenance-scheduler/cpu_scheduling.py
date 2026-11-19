"""
OS MODULE 1 - CPU SCHEDULING  (technician = CPU, maintenance job = process)
Algorithms: FCFS, SJF, SRTF, Priority (non-preemptive / preemptive, with AGING),
            Round Robin, HRRN, MLFQ.
Process dict: {pid, name, arrival, burst, priority}   (higher priority number = more urgent)
All times are integer hours.
"""
from collections import deque


def _prepare(procs):
    out = []
    for i, p in enumerate(procs):
        out.append({
            "pid": p.get("pid", i + 1),
            "name": p.get("name", f"J{i + 1}"),
            "arrival": int(p.get("arrival", 0)),
            "burst": max(1, int(p.get("burst", 1))),
            "priority": float(p.get("priority", 0)),
        })
    return out


def _push(gantt, name, pid, start, end):
    """Append a Gantt slice, merging with the previous one if same process."""
    if gantt and gantt[-1]["pid"] == pid and gantt[-1]["end"] == start:
        gantt[-1]["end"] = end
    else:
        gantt.append({"pid": pid, "name": name, "start": start, "end": end})


def _finish(algorithm, procs, gantt, first_start, completion, extra=None):
    rows, tw, tt, tr = [], 0, 0, 0
    for p in procs:
        ct = completion[p["pid"]]
        ta = ct - p["arrival"]
        wt = ta - p["burst"]
        rt = first_start[p["pid"]] - p["arrival"]
        tw += wt; tt += ta; tr += rt
        rows.append({**p, "completion": ct, "turnaround": ta, "waiting": wt, "response": rt})
    n = len(procs)
    busy = sum(g["end"] - g["start"] for g in gantt if g["pid"] is not None)
    span = (gantt[-1]["end"] - min(p["arrival"] for p in procs)) if gantt else 1
    switches = sum(1 for i in range(1, len(gantt))
                   if gantt[i]["pid"] != gantt[i - 1]["pid"] and gantt[i]["pid"] is not None
                   and gantt[i - 1]["pid"] is not None)
    res = {
        "algorithm": algorithm,
        "gantt": gantt,
        "processes": rows,
        "avg_waiting": round(tw / n, 2),
        "avg_turnaround": round(tt / n, 2),
        "avg_response": round(tr / n, 2),
        "context_switches": switches,
        "cpu_utilization": round(100 * busy / span, 2) if span else 100.0,
        "throughput": round(n / span, 3) if span else 0,
    }
    if extra:
        res.update(extra)
    return res


def fcfs(procs):
    procs = _prepare(procs)
    t, gantt, fs, comp = 0, [], {}, {}
    for p in sorted(procs, key=lambda x: (x["arrival"], x["pid"])):
        if t < p["arrival"]:
            _push(gantt, "IDLE", None, t, p["arrival"]); t = p["arrival"]
        fs[p["pid"]] = t
        _push(gantt, p["name"], p["pid"], t, t + p["burst"])
        t += p["burst"]; comp[p["pid"]] = t
    return _finish("FCFS", procs, gantt, fs, comp)


def _nonpreemptive(procs, key, label, extra_fn=None):
    procs = _prepare(procs)
    t, gantt, fs, comp, done = 0, [], {}, {}, set()
    while len(done) < len(procs):
        ready = [p for p in procs if p["pid"] not in done and p["arrival"] <= t]
        if not ready:
            nxt = min(p["arrival"] for p in procs if p["pid"] not in done)
            _push(gantt, "IDLE", None, t, nxt); t = nxt; continue
        p = min(ready, key=lambda x: key(x, t))
        fs[p["pid"]] = t
        _push(gantt, p["name"], p["pid"], t, t + p["burst"])
        t += p["burst"]; comp[p["pid"]] = t; done.add(p["pid"])
    return _finish(label, procs, gantt, fs, comp)


def sjf(procs):
    return _nonpreemptive(procs, lambda p, t: (p["burst"], p["arrival"], p["pid"]), "SJF")


def priority_np(procs):
    return _nonpreemptive(procs, lambda p, t: (-p["priority"], p["arrival"], p["pid"]), "Priority (NP)")


def hrrn(procs):
    """Highest Response Ratio Next: (waiting+burst)/burst - prevents starvation of long jobs."""
    return _nonpreemptive(
        procs, lambda p, t: (-((t - p["arrival"]) + p["burst"]) / p["burst"], p["arrival"], p["pid"]), "HRRN")


def _unit_step(procs, label, choose, on_tick=None):
    """Generic 1-hour-tick preemptive simulator. choose(ready, t, current)->process."""
    procs = _prepare(procs)
    rem = {p["pid"]: p["burst"] for p in procs}
    t, gantt, fs, comp = 0, [], {}, {}
    cur = None
    while len(comp) < len(procs):
        ready = [p for p in procs if p["pid"] not in comp and p["arrival"] <= t]
        if not ready:
            _push(gantt, "IDLE", None, t, t + 1); t += 1; cur = None; continue
        cur = choose(ready, rem, t, cur)
        fs.setdefault(cur["pid"], t)
        _push(gantt, cur["name"], cur["pid"], t, t + 1)
        rem[cur["pid"]] -= 1; t += 1
        if rem[cur["pid"]] == 0:
            comp[cur["pid"]] = t; cur = None
    return _finish(label, procs, gantt, fs, comp)


def srtf(procs):
    return _unit_step(procs, "SRTF",
                      lambda ready, rem, t, cur: min(ready, key=lambda p: (rem[p["pid"]], p["arrival"], p["pid"])))


def priority_p(procs, aging_interval=0):
    """Preemptive priority. aging_interval>0 => every N hours a job waits, its priority rises by 1
    (this removes STARVATION of low priority jobs)."""
    def eff(p, t):
        if aging_interval and aging_interval > 0:
            return p["priority"] + (t - p["arrival"]) // aging_interval
        return p["priority"]
    label = "Priority (P) + Aging" if aging_interval else "Priority (P)"
    return _unit_step(procs, label,
                      lambda ready, rem, t, cur: max(ready, key=lambda p: (eff(p, t), -p["arrival"], -p["pid"])))


def round_robin(procs, quantum=2):
    procs = _prepare(procs)
    quantum = max(1, int(quantum))
    order = sorted(procs, key=lambda x: (x["arrival"], x["pid"]))
    rem = {p["pid"]: p["burst"] for p in procs}
    q, t, i, gantt, fs, comp = deque(), 0, 0, [], {}, {}
    while len(comp) < len(procs):
        while i < len(order) and order[i]["arrival"] <= t:
            q.append(order[i]); i += 1
        if not q:
            nxt = order[i]["arrival"]
            _push(gantt, "IDLE", None, t, nxt); t = nxt; continue
        p = q.popleft()
        fs.setdefault(p["pid"], t)
        run = min(quantum, rem[p["pid"]])
        _push(gantt, p["name"], p["pid"], t, t + run)
        t += run; rem[p["pid"]] -= run
        while i < len(order) and order[i]["arrival"] <= t:   # arrivals during the slice enter first
            q.append(order[i]); i += 1
        if rem[p["pid"]] > 0:
            q.append(p)
        else:
            comp[p["pid"]] = t
    return _finish(f"Round Robin (q={quantum})", procs, gantt, fs, comp, {"quantum": quantum})


def mlfq(procs, quanta=(2, 4)):
    """3-level feedback queue: Q0 RR(q0) > Q1 RR(q1) > Q2 FCFS. New jobs enter Q0; using the
    whole quantum demotes the job one level. Higher queue always preempts lower queue."""
    procs = _prepare(procs)
    rem = {p["pid"]: p["burst"] for p in procs}
    level = {p["pid"]: 0 for p in procs}
    queues = [deque(), deque(), deque()]
    arrived, t, gantt, fs, comp = set(), 0, [], {}, {}
    cur, used = None, 0

    def admit():
        for p in sorted(procs, key=lambda x: (x["arrival"], x["pid"])):
            if p["arrival"] <= t and p["pid"] not in arrived:
                arrived.add(p["pid"]); queues[0].append(p)
    while len(comp) < len(procs):
        admit()
        if cur is not None:   # preempted by arrival into a higher queue?
            if any(queues[l] for l in range(level[cur["pid"]])):
                queues[level[cur["pid"]]].appendleft(cur); cur, used = None, 0
        if cur is None:
            for l in range(3):
                if queues[l]:
                    cur = queues[l].popleft(); used = 0; break
        if cur is None:
            _push(gantt, "IDLE", None, t, t + 1); t += 1; continue
        fs.setdefault(cur["pid"], t)
        _push(gantt, cur["name"], cur["pid"], t, t + 1)
        rem[cur["pid"]] -= 1; used += 1; t += 1
        if rem[cur["pid"]] == 0:
            comp[cur["pid"]] = t; cur = None
        else:
            lv = level[cur["pid"]]
            if lv < 2 and used >= quanta[lv]:
                level[cur["pid"]] = lv + 1
                admit(); queues[lv + 1].append(cur); cur = None
    return _finish("MLFQ (3 levels)", procs, gantt, fs, comp, {"quanta": list(quanta)})


ALGORITHMS = {
    "fcfs": lambda p, **k: fcfs(p),
    "sjf": lambda p, **k: sjf(p),
    "srtf": lambda p, **k: srtf(p),
    "priority": lambda p, **k: priority_np(p),
    "priority_p": lambda p, **k: priority_p(p, 0),
    "priority_aging": lambda p, **k: priority_p(p, k.get("aging_interval") or 3),
    "rr": lambda p, **k: round_robin(p, k.get("quantum", 2)),
    "hrrn": lambda p, **k: hrrn(p),
    "mlfq": lambda p, **k: mlfq(p),
}


def run(algorithm, procs, **kw):
    if algorithm not in ALGORITHMS:
        raise ValueError(f"unknown algorithm '{algorithm}'")
    return ALGORITHMS[algorithm](procs, **kw)


def compare_all(procs, quantum=2, aging_interval=3):
    res = [run(a, procs, quantum=quantum, aging_interval=aging_interval) for a in ALGORITHMS]
    best = min(res, key=lambda r: r["avg_waiting"])
    return {"results": res, "best_algorithm": best["algorithm"], "best_avg_waiting": best["avg_waiting"]}
