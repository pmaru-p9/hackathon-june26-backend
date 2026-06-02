import ipaddress


def ip_in_cidr(ip: str, cidr: str) -> bool:
    return ipaddress.ip_address(ip) in ipaddress.ip_network(cidr, strict=False)


class NeutronOps:
    def __init__(self, client):
        self.c = client

    def subnet_holds_free_ip(self, network_id: str, ip: str) -> bool:
        for s in self.c.subnets.values():
            if s["network_id"] == network_id and ip_in_cidr(ip, s["cidr"]):
                return ip not in s["allocated"]
        return False

    def create_port(self, network_id: str, fixed_ip: str, mac: str) -> str:
        return self.c.create_port(network_id, fixed_ip, mac)

    def delete_port(self, port_id: str) -> None:
        self.c.delete_port(port_id)
