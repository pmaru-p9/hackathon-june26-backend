from app.osclients.prod_clients import ProdNova


class FakeCompute:
    def __init__(self):
        self.create_kwargs = None
        self.calls = []

    def create_server(self, **kw):
        self.create_kwargs = kw
        return type("S", (), {"id": "dst-srv"})()

    # record positional args to assert SDK (server, volume) ordering
    def delete_volume_attachment(self, *args, **kw):
        self.calls.append(("delete_volume_attachment", args, kw))

    def update_volume_attachment(self, *args, **kw):
        self.calls.append(("update_volume_attachment", args, kw))


class FakeConn:
    def __init__(self):
        self.compute = FakeCompute()


def test_create_server_translates_to_sdk_kwargs():
    conn = FakeConn()
    nova = ProdNova(conn)
    out = nova.create_server(name="db", flavor="f1", ports=["port-x"],
                             block_device_mapping=["v1", "v2"], availability_zone="az1",
                             security_groups=["default"], key_name="kp", metadata={"a": "b"})
    assert out == {"id": "dst-srv"}
    kw = conn.compute.create_kwargs
    assert kw["name"] == "db" and kw["flavor_id"] == "f1"
    assert kw["networks"] == [{"port": "port-x"}]
    # no root_volume_id passed -> all data volumes: boot_index -1, dot False
    assert all(b["boot_index"] == -1 and b["delete_on_termination"] is False
               for b in kw["block_device_mapping_v2"])
    assert {b["uuid"] for b in kw["block_device_mapping_v2"]} == {"v1", "v2"}
    assert kw["security_groups"] == [{"name": "default"}]
    assert kw["availability_zone"] == "az1" and kw["key_name"] == "kp"


def test_create_server_sets_root_delete_on_termination():
    conn = FakeConn()
    ProdNova(conn).create_server(name="db", flavor="f", ports=["p"],
        block_device_mapping=["dv-root", "dv-data"], root_volume_id="dv-root",
        root_delete_on_termination=True, availability_zone="az", security_groups=[],
        key_name="k", metadata={})
    bdm = conn.compute.create_kwargs["block_device_mapping_v2"]
    root = next(b for b in bdm if b["uuid"] == "dv-root")
    data = next(b for b in bdm if b["uuid"] == "dv-data")
    assert root["delete_on_termination"] is True and root["boot_index"] == 0
    assert data["delete_on_termination"] is False and data["boot_index"] == -1


def test_attachment_calls_use_sdk_server_first_ordering():
    # regression: SDK is (server, volume); these were passed swapped, breaking VMs whose
    # root volume has delete_on_termination=True (C2b set_dot) and any data-volume detach.
    conn = FakeConn()
    nova = ProdNova(conn)
    nova.detach_volume("SERVER", "VOLUME")
    nova.set_attachment_dot("SERVER", "VOLUME", False)
    calls = {name: (args, kw) for name, args, kw in conn.compute.calls}
    assert calls["delete_volume_attachment"][0] == ("SERVER", "VOLUME")
    assert calls["update_volume_attachment"][0] == ("SERVER", "VOLUME")
