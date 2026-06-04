def match_flavor(flavors: list[dict], vcpus: int, ram: int, disk: int) -> dict | None:
    for f in flavors:
        if f["vcpus"] == vcpus and f["ram"] == ram and f["disk"] == disk:
            return f
    return None


class NovaOps:
    def __init__(self, client):
        self.c = client

    def stop(self, server_id: str) -> None:
        self.c.stop(server_id)

    def start(self, server_id: str) -> None:
        self.c.start(server_id)

    def detach_volume(self, server_id: str, volume_id: str) -> None:
        self.c.detach_volume(server_id, volume_id)

    def attach_volume(self, server_id: str, volume_id: str) -> None:
        self.c.attach_volume(server_id, volume_id)

    def create_server(self, **kw) -> dict:
        return self.c.create_server(**kw)

    def delete(self, server_id: str) -> None:
        self.c.delete(server_id)

    def server_status(self, server_id: str) -> str:
        return self.c.server_status(server_id)

    def dot(self, server_id: str, volume_id: str) -> bool:
        return self.c.attachment_dot(server_id, volume_id)

    def set_dot(self, server_id: str, volume_id: str, value: bool) -> None:
        self.c.set_attachment_dot(server_id, volume_id, value)

    def flavors(self) -> list[dict]:
        return list(self.c.flavors.values())
