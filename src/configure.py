"""Push IPv4/IPv6 addressing and OSPF to every router in configs/routers.yml."""
import os
import yaml
from netmiko import ConnectHandler

PASSWORD = os.environ.get("SRL_PASSWORD", "NokiaSrl1!")  # lab default


def build_commands(router):
    """Turn one router's data into the list of SR Linux CLI commands."""
    rid = router["router_id"]
    ospf = "set / network-instance default protocols ospf instance main"
    cmds = [
        "enter candidate private",  # start an edit session (nothing is live yet)
        "set / network-instance default type default",
        "set / network-instance default admin-state enable",
        f"set / network-instance default router-id {rid}",
        # system0 = loopback, the router's permanent address
        "set / interface system0 admin-state enable",
        "set / interface system0 subinterface 0 admin-state enable",
        "set / interface system0 subinterface 0 ipv4 admin-state enable",
        f"set / interface system0 subinterface 0 ipv4 address {rid}/32",
        "set / network-instance default interface system0.0",
        # OSPF: lets routers discover each other and share routes
        f"{ospf} admin-state enable",
        f"{ospf} version ospf-v2",
        f"{ospf} router-id {rid}",
        f"{ospf} area 0.0.0.0 interface system0.0 passive true",
    ]
    for name, addr in router["interfaces"].items():
        base = f"set / interface {name}"
        cmds += [
            f"{base} admin-state enable",
            f"{base} subinterface 0 admin-state enable",
            f"{base} subinterface 0 ipv4 admin-state enable",
            f"{base} subinterface 0 ipv4 address {addr['ipv4']}",
            f"{base} subinterface 0 ipv6 admin-state enable",
            f"{base} subinterface 0 ipv6 address {addr['ipv6']}",
            f"set / network-instance default interface {name}.0",
            f"{ospf} area 0.0.0.0 interface {name}.0 interface-type point-to-point",
        ]
    cmds.append("commit now")  # apply everything at once
    return cmds


def main():
    with open("configs/routers.yml") as f:
        routers = yaml.safe_load(f)["routers"]

    for name, router in routers.items():
        print(f"Configuring {name}...")
        conn = ConnectHandler(
            device_type="nokia_srl",
            host=router["host"],
            username="admin",
            password=PASSWORD,
        )
        output = conn.send_config_set(
            build_commands(router),
            enter_config_mode=False,
            exit_config_mode=False,
            cmd_verify=False,
            read_timeout=60,
        )
        conn.disconnect()
        if "committed" in output.lower():
            print(f"  OK: {name} configured")
        else:
            print(f"  WARNING: check {name}. Last output:\n{output[-800:]}")


if __name__ == "__main__":
    main()
