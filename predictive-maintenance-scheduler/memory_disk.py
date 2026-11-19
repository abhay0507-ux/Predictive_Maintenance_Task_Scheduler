"""
OS MODULE 4 - MEMORY & DISK MANAGEMENT
  * Page replacement : FIFO, LRU, Optimal  (reference string = machine sensor pages accessed)
  * LRUCache         : real cache used by the API for machine-health lookups (hit/miss stats)
  * Contiguous alloc : First-fit / Best-fit / Worst-fit (spare part storage bays)
  * Disk scheduling  : FCFS, SSTF, SCAN, C-SCAN, LOOK (sensor-log disk head movement)
"""
from collections import OrderedDict, deque
import threading


# ---------------- page replacement ----------------
def page_replacement(refs, frames, algo):
    mem, faults, steps = [], 0, []
    fifo = deque()
    lru = OrderedDict()
    for idx, page in enumerate(refs):
        hit = page in mem
        victim = None
        if not hit:
            faults += 1
            if len(mem) < frames:
                mem.append(page)
            else:
                if algo == "fifo":
                    victim = fifo.popleft()
                elif algo == "lru":
                    victim = next(iter(lru))
                else:  # optimal
                    future = refs[idx + 1:]
                    far, victim = -1, None
                    for pg in mem:
                        d = future.index(pg) if pg in future else 10 ** 9
                        if d > far: far, victim = d, pg
                mem[mem.index(victim)] = page
                lru.pop(victim, None)
            fifo.append(page)
        if algo == "lru":
            lru.pop(page, None); lru[page] = True
        steps.append({"page": page, "frames": list(mem), "hit": hit, "evicted": victim})
    n = len(refs)
    return {"algorithm": algo.upper(), "frames": frames, "page_faults": faults,
            "hits": n - faults, "hit_ratio": round(100 * (n - faults) / n, 2) if n else 0,
            "fault_ratio": round(100 * faults / n, 2) if n else 0, "steps": steps}


def compare_page_replacement(refs, frames):
    res = [page_replacement(refs, frames, a) for a in ("fifo", "lru", "optimal")]
    return {"results": res, "best": min(res, key=lambda r: r["page_faults"])["algorithm"]}


def belady_anomaly_demo():
    refs = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]
    return {"reference_string": refs,
            "fifo_3_frames": page_replacement(refs, 3, "fifo")["page_faults"],
            "fifo_4_frames": page_replacement(refs, 4, "fifo")["page_faults"],
            "note": "FIFO gives MORE faults with 4 frames than with 3 frames - Belady's anomaly"}


class LRUCache:
    """Thread-safe LRU cache (used by the backend for hot machine-health data)."""
    def __init__(self, capacity=8):
        self.capacity, self.data = capacity, OrderedDict()
        self.hits = self.misses = self.evictions = 0
        self.lock = threading.Lock()

    def get(self, key):
        with self.lock:
            if key in self.data:
                self.data.move_to_end(key); self.hits += 1
                return self.data[key]
            self.misses += 1
            return None

    def put(self, key, value):
        with self.lock:
            self.data[key] = value; self.data.move_to_end(key)
            if len(self.data) > self.capacity:
                self.data.popitem(last=False); self.evictions += 1

    def invalidate(self, key=None):
        with self.lock:
            if key is None: self.data.clear()
            else: self.data.pop(key, None)

    def stats(self):
        total = self.hits + self.misses
        return {"capacity": self.capacity, "size": len(self.data), "hits": self.hits,
                "misses": self.misses, "evictions": self.evictions,
                "hit_ratio": round(100 * self.hits / total, 2) if total else 0,
                "keys": list(self.data.keys())}


# ---------------- contiguous allocation ----------------
def contiguous_allocation(blocks, requests, strategy):
    blocks = list(blocks); orig = list(blocks)
    placements, internal_waste = [], 0
    for r in requests:
        cand = [i for i, b in enumerate(blocks) if b >= r]
        if not cand:
            placements.append({"request": r, "block": None}); continue
        if strategy == "first": i = cand[0]
        elif strategy == "best": i = min(cand, key=lambda k: blocks[k])
        else: i = max(cand, key=lambda k: blocks[k])
        blocks[i] -= r
        placements.append({"request": r, "block": i, "remaining_in_block": blocks[i]})
    return {"strategy": strategy + "-fit", "original_blocks": orig, "final_blocks": blocks,
            "placements": placements,
            "unallocated": sum(1 for p in placements if p["block"] is None),
            "external_fragmentation": sum(blocks)}


def compare_allocation(blocks, requests):
    res = [contiguous_allocation(blocks, requests, s) for s in ("first", "best", "worst")]
    return {"results": res,
            "best": min(res, key=lambda r: (r["unallocated"], r["external_fragmentation"]))["strategy"]}


# ---------------- disk scheduling ----------------
def disk_scheduling(requests, head, algo, disk_size=200, direction="up"):
    reqs = list(requests)
    order = []
    if algo == "fcfs":
        order = reqs
    elif algo == "sstf":
        pending, pos = reqs[:], head
        while pending:
            nxt = min(pending, key=lambda x: abs(x - pos)); order.append(nxt); pending.remove(nxt); pos = nxt
    elif algo in ("scan", "look"):
        lo = sorted(r for r in reqs if r < head); hi = sorted(r for r in reqs if r >= head)
        if direction == "up":
            order = hi + ([disk_size - 1] if algo == "scan" else []) + lo[::-1]
        else:
            order = lo[::-1] + ([0] if algo == "scan" else []) + hi
    elif algo in ("cscan", "clook"):
        lo = sorted(r for r in reqs if r < head); hi = sorted(r for r in reqs if r >= head)
        if algo == "cscan":
            order = hi + [disk_size - 1, 0] + lo
        else:
            order = hi + lo
    else:
        raise ValueError("unknown disk algorithm")
    pos, total, path = head, 0, [head]
    for x in order:
        total += abs(x - pos); pos = x; path.append(x)
    return {"algorithm": algo.upper(), "head_start": head, "order": order, "path": path,
            "total_head_movement": total}


def compare_disk(requests, head, disk_size=200, direction="up"):
    res = [disk_scheduling(requests, head, a, disk_size, direction)
           for a in ("fcfs", "sstf", "scan", "cscan", "look", "clook")]
    return {"results": res, "best": min(res, key=lambda r: r["total_head_movement"])["algorithm"]}
