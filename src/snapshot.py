"""Save a snapshot of network state (routes, OSPF neighbors, interfaces) from every router.

Usage: python3 src/snapshot.py <label>    e.g. before / after
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

import yaml
from netmiko import ConnectHandler

PASSWORD = os.environ.get("SRL_PASSWORD", "NokiaSrl1!")  # lab default

ROUTES_CMD = "info from state network-instance default route-table ipv4-unicast | as json"
OSPF_CMD = "show network-instance default protocols ospf neighbor"
INTF_CMD = "show interface brief"

NEIGHBOR_RE = re.compile(r"(ethernet-\S+)\s+(\d+\.\d+\.\d+\.\d+)\s+(\S+)")
INTF_RE = re.compile(r"\|\s*(ethernet-\S+|mgmt0)\s*\|\s*(enable|disable)\s*\|\s*(up|down)")


def get_routes(conn):
    """Routing table from JSON. Keep only fields that matter; timestamps would make every diff noisy."""
    data = json.loads(conn.send_command(ROUTES_CMD, read_timeout=60))
    routes = {}
    for r in data.get("route", []):
        if r["route-type"] == "host":
            continue  # per-address host entries add noise, skip them
        routes[r["ipv4-prefix"]] = {
            "type": r["route-type"],
            "metric": r["metric"],
            "active": r["active"],
        }
    return routes


def get_ospf_neighbors(conn):
    """OSPF neighbor table, keyed by neighbor router ID."""
    out = conn.send_command(OSPF_CMD)
    return {rid: {"interface": intf, "state": state}
            for intf, rid, state in NEIGHBOR_RE.findall(out)}


def get_interfaces(conn):
    """Admin and operational state of every port."""
    out = conn.send_command(INTF_CMD)
    return {name: {"admin": admin, "oper": oper}
            for name, admin, oper in INTF_RE.findall(out)}


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "snapshot"
    with open("configs/routers.yml") as f:
        routers = yaml.safe_load(f)["routers"]

    snapshot = {"taken_at": datetime.now(timezone.utc).isoformat(), "routers": {}}

    for name, router in routers.items():
        conn = ConnectHandler(device_type="nokia_srl", host=router["host"],
                              username="admin", password=PASSWORD)
        state = {
            "routes": get_routes(conn),
            "ospf_neighbors": get_ospf_neighbors(conn),
            "interfaces": get_interfaces(conn),
        }
        conn.disconnect()
        snapshot["routers"][name] = state
        up = sum(1 for i in state["interfaces"].values() if i["oper"] == "up")
        print(f"{name}: {len(state['routes'])} routes, "
              f"{len(state['ospf_neighbors'])} OSPF neighbors, {up} interfaces up")

    os.makedirs("snapshots", exist_ok=True)
    path = f"snapshots/{label}.json"
    with open(path, "w") as f:
        json.dump(snapshot, f, indent=2, sort_keys=True)
    print(f"Saved {path}")


if __name__ == "__main__":
    main()
