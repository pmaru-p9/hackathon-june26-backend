class SecretStore:
    def __init__(self, client):
        self.c = client

    def write(self, ns, name, kv):
        self.c.write(ns, name, kv)

    def read(self, ns, name):
        return self.c.read(ns, name)

    def delete(self, ns, name):
        self.c.delete(ns, name)
