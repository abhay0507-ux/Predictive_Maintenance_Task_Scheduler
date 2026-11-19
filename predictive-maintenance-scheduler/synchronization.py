"""
OS MODULE 2 - PROCESS SYNCHRONIZATION
  * Counting SEMAPHORE  : technician pool (K technicians shared by N job-threads)
  * MUTEX (Lock)        : protects the shared spare-parts stock (critical section)
  * Race-condition demo : same workload WITHOUT and WITH the mutex
  * PRODUCER-CONSUMER   : sensor producers -> bounded buffer -> analyser consumers
  * READERS-WRITERS     : dashboard readers vs. inventory writers
Everything uses real Python threads; events are timestamped so the UI can show them.
"""
import threading, time, random, queue


def technician_semaphore_demo(num_jobs=8, num_technicians=3, work_ms=120):
    sem = threading.BoundedSemaphore(num_technicians)
    lock = threading.Lock()
    events, state = [], {"busy": 0, "max_busy": 0}
    t0 = time.perf_counter()

    def log(msg):
        with lock:
            events.append({"t_ms": round((time.perf_counter() - t0) * 1000), "event": msg})

    def job(i):
        log(f"Job J{i} WAIT   (P operation)")
        sem.acquire()
        with lock:
            state["busy"] += 1
            state["max_busy"] = max(state["max_busy"], state["busy"])
            busy = state["busy"]
        log(f"Job J{i} ENTER  (technicians busy = {busy}/{num_technicians})")
        time.sleep(work_ms / 1000 * random.uniform(0.8, 1.4))
        with lock:
            state["busy"] -= 1
        log(f"Job J{i} SIGNAL (V operation) - technician freed")
        sem.release()

    threads = [threading.Thread(target=job, args=(i + 1,)) for i in range(num_jobs)]
    for th in threads: th.start()
    for th in threads: th.join()
    return {"demo": "Counting semaphore - technician pool", "jobs": num_jobs,
            "technicians": num_technicians, "max_concurrent": state["max_busy"],
            "limit_respected": state["max_busy"] <= num_technicians, "events": events}


def race_condition_demo(threads=8, iterations=2000):
    """Classic lost-update: many threads decrement the same stock counter."""
    start_stock = threads * iterations

    def run(use_lock):
        stock = {"v": start_stock}
        lock = threading.Lock()

        def worker():
            for _ in range(iterations):
                if use_lock:
                    with lock:
                        stock["v"] = stock["v"] - 1
                else:
                    cur = stock["v"]
                    if random.random() < 0.002:
                        time.sleep(0)          # force a context switch inside the critical section
                    stock["v"] = cur - 1
        ths = [threading.Thread(target=worker) for _ in range(threads)]
        for th in ths: th.start()
        for th in ths: th.join()
        return stock["v"]

    without, with_lock = run(False), run(True)
    return {"demo": "Race condition vs mutex", "expected_final_stock": 0,
            "without_mutex_final": without, "with_mutex_final": with_lock,
            "race_detected": without != 0, "mutex_correct": with_lock == 0,
            "lost_updates_without_mutex": without}


def producer_consumer_demo(producers=2, consumers=2, items_per_producer=6, buffer_size=3):
    buf = queue.Queue(maxsize=buffer_size)            # bounded buffer (empty/full semaphores inside)
    lock = threading.Lock()
    events, t0 = [], time.perf_counter()
    consumed = []

    def log(m):
        with lock:
            events.append({"t_ms": round((time.perf_counter() - t0) * 1000), "event": m})

    def producer(pid):
        for k in range(items_per_producer):
            item = f"S{pid}-{k + 1}"
            buf.put(item)                              # blocks when buffer FULL
            log(f"Sensor-{pid} PRODUCED {item} (buffer={buf.qsize()}/{buffer_size})")
            time.sleep(random.uniform(0.01, 0.04))

    def consumer(cid):
        while True:
            item = buf.get()                           # blocks when buffer EMPTY
            if item is None:
                buf.task_done(); return
            time.sleep(random.uniform(0.03, 0.07))
            with lock: consumed.append(item)
            log(f"Analyser-{cid} CONSUMED {item}")
            buf.task_done()

    pts = [threading.Thread(target=producer, args=(i + 1,)) for i in range(producers)]
    cts = [threading.Thread(target=consumer, args=(i + 1,)) for i in range(consumers)]
    for th in pts + cts: th.start()
    for th in pts: th.join()
    for _ in cts: buf.put(None)
    for th in cts: th.join()
    total = producers * items_per_producer
    return {"demo": "Producer-Consumer (bounded buffer)", "produced": total, "consumed": len(consumed),
            "no_item_lost": total == len(consumed), "buffer_size": buffer_size, "events": events[:60]}


def readers_writers_demo(readers=4, writers=2, rounds=3):
    """Readers-preference solution: many readers may read together, a writer needs exclusive access."""
    read_count, mutex, rw_lock = [0], threading.Lock(), threading.Lock()
    events, ev_lock, t0 = [], threading.Lock(), time.perf_counter()
    stats = {"max_parallel_readers": 0, "violations": 0, "writing": False}

    def log(m):
        with ev_lock:
            events.append({"t_ms": round((time.perf_counter() - t0) * 1000), "event": m})

    def reader(i):
        for _ in range(rounds):
            with mutex:
                if read_count[0] == 0: rw_lock.acquire()   # first reader locks writers out
                read_count[0] += 1
                stats["max_parallel_readers"] = max(stats["max_parallel_readers"], read_count[0])
                if stats["writing"]: stats["violations"] += 1
            log(f"Reader-{i} READING dashboard (readers={read_count[0]})")
            time.sleep(0.03)
            with mutex:
                read_count[0] -= 1
                if read_count[0] == 0: rw_lock.release()
            time.sleep(random.uniform(0.005, 0.02))

    def writer(i):
        for _ in range(rounds):
            rw_lock.acquire()
            stats["writing"] = True
            if read_count[0] > 0: stats["violations"] += 1
            log(f"Writer-{i} UPDATING inventory (exclusive)")
            time.sleep(0.04)
            stats["writing"] = False
            rw_lock.release()
            time.sleep(random.uniform(0.01, 0.03))
    ths = [threading.Thread(target=reader, args=(i + 1,)) for i in range(readers)] + \
          [threading.Thread(target=writer, args=(i + 1,)) for i in range(writers)]
    for th in ths: th.start()
    for th in ths: th.join()
    return {"demo": "Readers-Writers", "max_parallel_readers": stats["max_parallel_readers"],
            "violations": stats["violations"], "safe": stats["violations"] == 0, "events": events[:60]}
