"""Container-level network optimizer with deadlines and demurrage.

Assigns each inbound container to one building and one day, or defers it, to
maximize expected demand coverage at a service level. ETAs are exogenous inputs
(assigned by the carrier, not chosen): a container cannot be unloaded before it
arrives, and it must be unloaded on or before its deadline. Deferring past free
time accrues demurrage.

The priority order, applied per day, is:

  0. Deadline. Containers due today are forced out first. This is a hard
     constraint, above the objective; if more are due than the daily limit
     allows, the overflow is flagged as a deadline violation.
  1. Coverage. Demand first, always: fill remaining slots with the containers
     that cover the most service-level demand.
  2. Ease. Break coverage ties by purity, then SKU count, then cube, then which
     container is closest to accruing demurrage.
  3. Demurrage avoidance. Only if a slot would otherwise sit idle, use it on a
     container already past free time, to stop the bleeding. Idle capacity is
     never used to unload something that neither covers demand nor is accruing.

Greedy is appropriate because demand coverage is monotone and submodular, and
greedy selection under a per-day limit is submodular maximization under a matroid
constraint with the classical (1 - 1/e) guarantee (Nemhauser, Wolsey, Fisher 1978).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Result:
    assignments: list = field(default_factory=list)
    deferred: list = field(default_factory=list)
    visitors: dict = field(default_factory=dict)
    remaining: dict = field(default_factory=dict)
    required_total: float = 0.0
    demurrage_cost: float = 0.0
    violations: list = field(default_factory=list)


def _evaluate(contents_c, remaining, home):
    per_b, total_units, homed_units = {}, 0, {}
    for item, qty in contents_c.items():
        b = home[item]
        per_b[b] = per_b.get(b, 0.0) + min(qty, max(0.0, remaining.get(item, 0.0)))
        homed_units[b] = homed_units.get(b, 0) + qty
        total_units += qty
    best_b = max(per_b, key=per_b.get)
    purity = homed_units.get(best_b, 0) / total_units if total_units else 0.0
    return best_b, per_b[best_b], purity, len(contents_c)


def schedule(data, required, strategy="greedy", eps=0.08):
    home = dict(zip(data["items"].item_id, data["items"].home))
    contents = {cid: dict(zip(g.item_id, g.qty))
                for cid, g in data["contents"].groupby("container_id")}
    c = data["containers"]
    eta = dict(zip(c.container_id, c.eta_day))
    cbm = dict(zip(c.container_id, c.cbm))
    free_until = dict(zip(c.container_id, c.free_until))
    deadline = dict(zip(c.container_id, c.deadline))
    demur = dict(zip(c.container_id, c.demurrage_per_day))
    cap, horizon = data["capacity"], data["horizon"]

    remaining = dict(required)
    res = Result(remaining=remaining, required_total=sum(required.values()))
    scheduled = set()

    def commit(cid, b, d, cov, purity, nsku, reason):
        offhome = 0
        for item, qty in contents[cid].items():
            if home[item] == b:
                remaining[item] = max(0.0, remaining.get(item, 0.0) - qty)
            else:
                offhome += qty
        dem = max(0, d - free_until[cid]) * demur[cid]
        res.assignments.append({"container": cid, "building": b, "day": d,
                                "coverage": round(cov, 1), "purity": round(purity, 2),
                                "nsku": nsku, "reason": reason, "demurrage": round(dem, 2)})
        res.visitors[cid] = offhome
        res.demurrage_cost += dem
        scheduled.add(cid)

    def score(cid):
        b, cov, purity, nsku = _evaluate(contents[cid], remaining, home)
        return (cid, b, cov, purity, nsku)

    for d in range(horizon):
        used = 0
        eligible = [x for x in contents if x not in scheduled and eta[x] <= d and d <= deadline[x]]

        # 0. Deadline feasibility (earliest-deadline-first). Schedule the minimum
        #    number needed today so no future deadline becomes impossible, and no
        #    more, so demand-first still governs the remaining slots. This is the
        #    classic EDF feasibility rule.
        elig_sorted = sorted(eligible, key=lambda x: deadline[x])
        must, seen, i, n = 0, 0, 0, len(elig_sorted)
        while i < n:
            D = deadline[elig_sorted[i]]
            while i < n and deadline[elig_sorted[i]] == D:
                seen += 1
                i += 1
            must = max(must, seen - cap * (D - d))
        must_today = max(0, min(cap, must))
        crit = sorted((score(x) for x in eligible), key=lambda s: (deadline[s[0]], -s[2], -s[3]))
        for cid, b, cov, purity, nsku in crit[:must_today]:
            if used >= cap:
                break
            commit(cid, b, d, cov, purity, nsku, "deadline_critical")
            used += 1

        # 1-3. Discretionary fill.
        while used < cap:
            disc = [score(x) for x in eligible if x not in scheduled]
            if not disc:
                break
            positive = [s for s in disc if s[2] > 0]
            if positive:
                if strategy == "greedy":
                    best_cov = max(s[2] for s in positive)
                    band = [s for s in positive if s[2] >= best_cov * (1 - eps)]
                    # Within a few percent of best coverage, prefer the container
                    # already bleeding demurrage, highest rate first. Demand still
                    # governs; this only chooses among near-equal options.
                    band.sort(key=lambda s: (0 if free_until[s[0]] <= d else 1,
                                             -demur[s[0]], -s[2], -s[3], s[4], cbm[s[0]]))
                    cid, b, cov, purity, nsku = band[0]
                else:
                    positive.sort(key=lambda s: (eta[s[0]], cbm[s[0]]))
                    cid, b, cov, purity, nsku = positive[0]
                commit(cid, b, d, cov, purity, nsku, "selected_for_coverage")
                used += 1
            else:
                accruing = [s for s in disc if free_until[s[0]] <= d]
                if not accruing:
                    break                      # leave the slot idle rather than unload pointlessly
                accruing.sort(key=lambda s: (free_until[s[0]], -demur[s[0]]))
                cid, b, cov, purity, nsku = accruing[0]
                commit(cid, b, d, cov, purity, nsku, "demurrage_avoidance")
                used += 1

    for cid in contents:
        if cid in scheduled:
            continue
        if deadline[cid] < horizon:
            res.violations.append(cid)
            res.deferred.append({"container": cid, "reason": "deadline_missed"})
        else:
            _, cov, _, _ = _evaluate(contents[cid], remaining, home)
            res.deferred.append({"container": cid,
                                 "reason": "demand_already_met" if cov <= 0 else "beyond_horizon"})
    return res
