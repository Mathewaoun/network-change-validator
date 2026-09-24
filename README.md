# Network Change Validator

Most network outages happen right after a configuration change. Something breaks quietly (a route disappears, a neighbor drops) and nobody notices until users complain.

This tool snapshots network state **before and after a change**, compares them, and reports exactly what broke, ranked by severity.

## Demo

One interface was shut down on `r1`. The tool flagged 10 changes across all 3 routers, including a lost route on `r2`, a router nobody touched:

```
[CRITICAL] r1: interface ethernet-1/2 went down
[CRITICAL] r1: lost OSPF neighbor 10.255.0.3 on ethernet-1/2.0
[CRITICAL] r1: lost route to 10.0.13.0/24 (local)
[CRITICAL] r2: lost route to 10.0.13.0/24 (ospfv2)
[CRITICAL] r3: interface ethernet-1/2 went down
[CRITICAL] r3: lost OSPF neighbor 10.255.0.1 on ethernet-1/2.0
[CRITICAL] r3: lost route to 10.0.13.0/24 (local)
[WARNING ] r1: interface ethernet-1/2 admin enable -> disable
[WARNING ] r1: route to 10.255.0.3/32 rerouted: metric 16 -> 32
[WARNING ] r3: route to 10.255.0.1/32 rerouted: metric 16 -> 32

Summary: 7 critical, 3 warning, 0 info
```

The warnings show the network **rerouting through r2**: it survived, but on a longer path.

## Lab topology

Three Nokia SR Linux routers in a triangle, running OSPF, with IPv4 and IPv6 on every link:

```
            r1 (10.255.0.1)
           /              \
   10.0.12.0/24       10.0.13.0/24
         /                  \
 r2 (10.255.0.2) ---- r3 (10.255.0.3)
          10.0.23.0/24
```

## How it works

| Script | What it does |
|---|---|
| `src/configure.py` | Reads `configs/routers.yml` and pushes IPv4/IPv6 addressing and OSPF to every router over SSH |
| `src/snapshot.py` | Collects routes, OSPF neighbors, and interface states from every router and saves them as JSON |
| `src/compare.py` | Diffs two snapshots and reports changes as CRITICAL, WARNING, or INFO. Exits with code 1 on any critical finding |

## Design decisions

- **Data separate from code.** All addressing lives in `configs/routers.yml`. Changing the network means editing data, not Python.
- **Structured data over screen scraping.** Routes are collected as JSON from the router's state model, because `show` output formats change between software versions.
- **Noise filtered out.** Timestamps and host routes are dropped from snapshots so that only real changes appear in a diff.
- **Automation-ready.** `compare.py` exits non-zero on critical findings, so it can gate a deployment or trigger a rollback in a CI pipeline.
- **No secrets in code.** The router password is read from the `SRL_PASSWORD` environment variable.

## Run it yourself

Requirements: Linux (or a Linux VM), Docker, [Containerlab](https://containerlab.dev), Python 3.

```bash
# 1. Start the lab
containerlab deploy -t lab/netlab.clab.yml

# 2. Set up Python
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Configure the network
python3 src/configure.py

# 4. Snapshot, make a change, snapshot again, compare
python3 src/snapshot.py before
# ... make a change ...
python3 src/snapshot.py after
python3 src/compare.py snapshots/before.json snapshots/after.json
```

## Tech stack

Python · Netmiko · Nokia SR Linux · Containerlab · Docker · OSPF · IPv4/IPv6

## Roadmap

- [ ] Automated tests with pytest
- [ ] Slack alerts on critical findings
- [ ] OSPFv3 for IPv6 routing
- [ ] Web dashboard for before/after results
