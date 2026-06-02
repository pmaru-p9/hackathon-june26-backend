class DiscoveryService:
    """Builds a destination connection from saved creds (conn_factory) and exposes
    live discovery. conn_factory(destination_id) -> connection object."""

    def __init__(self, conn_factory, draft_conn_factory=None):
        self.conn_factory = conn_factory
        # draft_conn_factory(creds_dict) -> connection, for validating unsaved creds
        self.draft_conn_factory = draft_conn_factory

    def test(self, did):
        try:
            self.conn_factory(did).authorize()
            return (True, "ok")
        except Exception as exc:  # noqa: BLE001
            return (False, str(exc))

    def test_draft(self, creds: dict):
        """Validate not-yet-saved destination credentials (used by the registration
        form's 'Test connection' before the destination exists)."""
        try:
            self.draft_conn_factory(creds).authorize()
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
