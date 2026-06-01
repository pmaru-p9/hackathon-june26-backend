import copy
class FakeCustomObjects:
    def __init__(self): self.store = {}
    def create(self, ns, kind, body):
        self.store[(ns, kind, body["metadata"]["name"])] = copy.deepcopy(body)
    def get(self, ns, kind, name): return copy.deepcopy(self.store[(ns, kind, name)])
    def list(self, ns, kind):
        return [copy.deepcopy(v) for (n, k, _), v in self.store.items() if n == ns and k == kind]
    def patch(self, ns, kind, name, body):
        self.store[(ns, kind, name)].update(copy.deepcopy(body))
    def delete(self, ns, kind, name): self.store.pop((ns, kind, name), None)
class FakeSecrets:
    def __init__(self): self.data = {}
    def write(self, ns, name, kv): self.data[(ns, name)] = dict(kv)
    def read(self, ns, name): return dict(self.data[(ns, name)])
    def delete(self, ns, name): self.data.pop((ns, name), None)
