class FakeCinder:
    def __init__(self):
        self.volumes = {}            # id -> dict
        self._unmanaged = {}         # host -> [reference dicts]
        self.managed_on = []         # record of manage() calls
    def add_volume(self, vid, size, host, bootable, backend_name, attached_to=None):
        self.volumes[vid] = dict(id=vid, size=size, host=host, bootable=bootable,
                                 backend_name=backend_name, status="available",
                                 attached_to=attached_to)
    def unmanage(self, vid):
        v = self.volumes.pop(vid)
        self._unmanaged.setdefault(v["host"], []).append(
            {"reference": {"source-name": v["backend_name"]}, "size": v["size"],
             "safe_to_manage": True})
    def list_manageable(self, host):
        return list(self._unmanaged.get(host, []))
    def manage(self, host, ref, name, volume_type, bootable, availability_zone, metadata=None):
        nid = f"dst-{name}"
        self.managed_on.append(dict(host=host, ref=ref, volume_type=volume_type,
                                    bootable=bootable, az=availability_zone))
        self.volumes[nid] = dict(id=nid, host=host, bootable=bootable, status="available")
        return dict(id=nid)
    def set_image_metadata(self, vid, meta): self.volumes[vid]["image_meta"] = meta
    def services(self): return [{"binary": "cinder-volume", "host": "h@be", "state": "up"}]
    def pools(self): return [{"name": "h@be#pool", "backend_name": "be"}]

class FakeNova:
    def __init__(self):
        self.servers = {}; self.flavors = {}; self.stopped = []; self.created = []
        self.detached = []; self.deleted = []
    def add_server(self, sid, **kw): self.servers[sid] = dict(id=sid, **kw)
    def add_flavor(self, fid, name, vcpus, ram, disk):
        self.flavors[fid] = dict(id=fid, name=name, vcpus=vcpus, ram=ram, disk=disk)
    def stop(self, sid): self.stopped.append(sid); self.servers[sid]["status"] = "SHUTOFF"
    def detach_volume(self, sid, vid): self.detached.append((sid, vid))
    def create_server(self, **kw):
        sid = "dst-srv"; self.created.append(kw)
        self.servers[sid] = dict(id=sid, status="ACTIVE", **kw); return dict(id=sid)
    def delete(self, sid): self.deleted.append(sid); self.servers.pop(sid, None)

class FakeNeutron:
    def __init__(self): self.ports = {}; self.subnets = {}
    def add_subnet(self, sid, network_id, cidr, allocated=None):
        self.subnets[sid] = dict(id=sid, network_id=network_id, cidr=cidr,
                                 allocated=set(allocated or []))
    def create_port(self, network_id, fixed_ip, mac):
        pid = f"port-{fixed_ip}"; self.ports[pid] = dict(id=pid, network_id=network_id,
                                                         fixed_ip=fixed_ip, mac=mac); return pid
    def delete_port(self, pid): self.ports.pop(pid, None)
