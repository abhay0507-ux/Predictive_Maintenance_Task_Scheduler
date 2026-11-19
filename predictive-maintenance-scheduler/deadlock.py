"""
OS MODULE 3 - DEADLOCK (spare-part resources)
  * Banker's algorithm  : safety check + resource-request simulation (deadlock AVOIDANCE)
  * Deadlock DETECTION  : wait-for / detection algorithm on current allocation
  Processes = maintenance jobs, Resources = spare-part types, instances = stock quantity.
"""


def safety_check(available, maximum, allocation):
    n, m = len(maximum), len(available)
    need = [[maximum[i][j] - allocation[i][j] for j in range(m)] for i in range(n)]
    work, finish, seq, steps = list(available), [False] * n, [], []
    progress = True
    while progress:
        progress = False
        for i in range(n):
            if not finish[i] and all(need[i][j] <= work[j] for j in range(m)):
                steps.append({"process": i, "work_before": list(work), "need": list(need[i])})
                work = [work[j] + allocation[i][j] for j in range(m)]
                finish[i] = True; seq.append(i); progress = True
    return {"safe": all(finish), "safe_sequence": seq if all(finish) else [],
            "need": need, "steps": steps, "unfinished": [i for i in range(n) if not finish[i]]}


def request_resources(available, maximum, allocation, pid, request):
    """Banker's resource-request algorithm. Grants only if the resulting state is SAFE."""
    m = len(available)
    need = [maximum[pid][j] - allocation[pid][j] for j in range(m)]
    if any(request[j] > need[j] for j in range(m)):
        return {"granted": False, "reason": "Request exceeds the process's declared maximum claim"}
    if any(request[j] > available[j] for j in range(m)):
        return {"granted": False, "reason": "Resources not available - process must wait"}
    new_av = [available[j] - request[j] for j in range(m)]
    new_alloc = [row[:] for row in allocation]
    for j in range(m): new_alloc[pid][j] += request[j]
    chk = safety_check(new_av, maximum, new_alloc)
    if chk["safe"]:
        return {"granted": True, "reason": "Resulting state is SAFE - request granted",
                "safe_sequence": chk["safe_sequence"]}
    return {"granted": False, "reason": "Granting would leave the system in an UNSAFE state (deadlock risk)"}


def detect_deadlock(available, allocation, request):
    """Deadlock detection: processes that can never get their pending request are deadlocked."""
    n, m = len(allocation), len(available)
    work, finish = list(available), [all(a == 0 for a in allocation[i]) for i in range(n)]
    progress = True
    while progress:
        progress = False
        for i in range(n):
            if not finish[i] and all(request[i][j] <= work[j] for j in range(m)):
                work = [work[j] + allocation[i][j] for j in range(m)]
                finish[i] = True; progress = True
    dead = [i for i in range(n) if not finish[i]]
    return {"deadlocked": bool(dead), "deadlocked_processes": dead}


def analyse(resources, processes, available):
    """resources: [names]; processes: [{name, maximum[], allocation[]}]; available: []"""
    maximum = [p["maximum"] for p in processes]
    allocation = [p["allocation"] for p in processes]
    res = safety_check(available, maximum, allocation)
    res["resources"] = resources
    res["processes"] = [p["name"] for p in processes]
    res["safe_sequence_names"] = [processes[i]["name"] for i in res["safe_sequence"]]
    res["unfinished_names"] = [processes[i]["name"] for i in res["unfinished"]]
    return res
