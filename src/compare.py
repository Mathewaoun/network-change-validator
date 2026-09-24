"""Compare two network snapshots and report what changed.

Usage: python3 src/compare.py snapshots/before.json snapshots/after.json
Exits with code 1 if anything CRITICAL is found, so it can be used in automation.
"""
import json
import sys

CRITICAL, WARNING, INFO = "CRITICAL", "WARNING", "INFO"
SEVERITY_ORDER = {CRITICAL: 0, WARNING: 1, INFO: 2}


def compare_routes(router, before, after):
    findings = []
    for prefix, b in before.items():
        a = after.get(prefix)
        if a is None:
            findings.append((CRITICAL, router, f"lost route to {prefix} ({b['type']})"))
        elif a["metric"] != b["metric"]:
            findings.append((WARNING, router,
                             f"route to {prefix} rerouted: metric {b['metric']} -> {a['metric']}"))
        elif a["active"] != b["active"]:
            level = INFO if a["active"] else CRITICAL
            findings.append((level, router,
                             f"route to {prefix} active: {b['active']} -> {a['active']}"))
    for prefix in sorted(after.keys() - before.keys()):
        findings.append((INFO, router, f"new route to {prefix} ({after[prefix]['type']})"))
    return findings


def compare_neighbors(router, before, after):
    findings = []
    for rid, b in before.items():
        a = after.get(rid)
        if a is None:
            findings.append((CRITICAL, router,
                             f"lost OSPF neighbor {rid} on {b['interface']}"))
        elif a["state"] != b["state"]:
            level = CRITICAL if b["state"] == "full" else WARNING
            findings.append((level, router,
                             f"OSPF neighbor {rid} state {b['state']} -> {a['state']}"))
    for rid in sorted(after.keys() - before.keys()):
        findings.append((INFO, router, f"new OSPF neighbor {rid}"))
    return findings


def compare_interfaces(router, before, after):
    findings = []
    for name, b in before.items():
        a = after.get(name)
        if a is None:
            findings.append((WARNING, router, f"interface {name} missing"))
            continue
        if a["oper"] != b["oper"]:
            level = CRITICAL if a["oper"] == "down" else INFO
            findings.append((level, router, f"interface {name} went {a['oper']}"))
        if a["admin"] != b["admin"]:
            findings.append((WARNING, router,
                             f"interface {name} admin {b['admin']} -> {a['admin']}"))
    return findings


def main():
    if len(sys.argv) != 3:
        sys.exit("Usage: python3 src/compare.py <before.json> <after.json>")

    with open(sys.argv[1]) as f:
        before = json.load(f)
    with open(sys.argv[2]) as f:
        after = json.load(f)

    findings = []
    for router, b in before["routers"].items():
        a = after["routers"].get(router)
        if a is None:
            findings.append((CRITICAL, router, "router missing from after snapshot"))
            continue
        findings += compare_interfaces(router, b["interfaces"], a["interfaces"])
        findings += compare_neighbors(router, b["ospf_neighbors"], a["ospf_neighbors"])
        findings += compare_routes(router, b["routes"], a["routes"])

    findings.sort(key=lambda f: (SEVERITY_ORDER[f[0]], f[1]))

    print(f"Comparing {before['taken_at']}  ->  {after['taken_at']}\n")
    if not findings:
        print("No changes detected. Network is healthy.")
        return

    for level, router, message in findings:
        print(f"[{level:8}] {router}: {message}")

    counts = {lvl: sum(1 for f in findings if f[0] == lvl) for lvl in SEVERITY_ORDER}
    print(f"\nSummary: {counts[CRITICAL]} critical, {counts[WARNING]} warning, {counts[INFO]} info")
    if counts[CRITICAL]:
        sys.exit(1)


if __name__ == "__main__":
    main()
