GROUP = "migration.pf9.io"
VERSION = "v1alpha1"
PLURALS = {"DestinationPCD": "destinationpcds", "Migration": "migrations"}


class CrdStore:
    """Adapter over kubernetes CustomObjectsApi; in tests, over FakeCustomObjects."""

    def __init__(self, client):
        self.c = client

    def create(self, ns, kind, body):
        self.c.create(ns, kind, body)
        return body

    def get(self, ns, kind, name):
        return self.c.get(ns, kind, name)

    def list(self, ns, kind):
        return self.c.list(ns, kind)

    def patch(self, ns, kind, name, body):
        self.c.patch(ns, kind, name, body)

    def delete(self, ns, kind, name):
        self.c.delete(ns, kind, name)
