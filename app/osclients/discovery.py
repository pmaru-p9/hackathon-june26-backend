class DiscoveryService:
    """Builds a destination connection from saved creds (conn_factory) and exposes
    live discovery. conn_factory(destination_id) -> connection object."""

    def __init__(self, conn_factory):
        self.conn_factory = conn_factory

    def test(self, did):
        try:
            self.conn_factory(did).authorize()
            return (True, "ok")
        except Exception as exc:  # noqa: BLE001
            return (False, str(exc))

    def projects(self, did):
        return self.conn_factory(did).projects()

    def azs(self, did):
        return self.conn_factory(did).azs()

    def networks(self, did):
        return self.conn_factory(did).networks()

    def flavors(self, did):
        return self.conn_factory(did).flavors()
