from app.osclients.prod_clients import ProdNova


class FakeCompute:
    def __init__(self):
        self.create_kwargs = None

    def create_server(self, **kw):
        self.create_kwargs = kw
        return type("S", (), {"id": "dst-srv"})()


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
    assert kw["block_device_mapping_v2"][0] == {
        "uuid": "v1", "source_type": "volume", "destination_type": "volume",
        "boot_index": 0, "delete_on_termination": False}
    assert kw["block_device_mapping_v2"][1]["boot_index"] == 1
    assert kw["security_groups"] == [{"name": "default"}]
    assert kw["availability_zone"] == "az1" and kw["key_name"] == "kp"
