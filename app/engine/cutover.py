from app.engine.base import StepResult
from app.config import settings


def cutover(nova, cinder, server_id, volume_ids, dest_port_ids, flavor_id, az,
            volume_type, sgs, keypair, metadata, name, root_volume_id, image_meta) -> list:
    results = []
    nova.stop(server_id)                                                 # C1
    results.append(StepResult("C1", ok=True, checkpoint={"wasRunning": True}))

    for vid in volume_ids:                                               # C2
        nova.detach_volume(server_id, vid)
    results.append(StepResult("C2", ok=True, checkpoint={"detached": list(volume_ids)}))

    unmanaged = [cinder.unmanage(vid) for vid in volume_ids]             # C3
    results.append(StepResult("C3", ok=True, checkpoint={"unmanaged": unmanaged}))

    pool = cinder.resolve_pool()                                         # C4
    dest_vol_ids = []
    for vid, backend_name in zip(volume_ids, unmanaged):
        ref = cinder.wait_for_manageable(pool, backend_name,
                                         attempts=settings.manageable_poll_attempts, delay=0)
        new = cinder.manage(host=pool, ref=ref, name=vid, volume_type=volume_type,
                            bootable=(vid == root_volume_id), az=az)
        if vid == root_volume_id:
            cinder.set_image_metadata(new["id"], image_meta)
        dest_vol_ids.append(new["id"])
    results.append(StepResult("C4", ok=True, checkpoint={"destVolIds": dest_vol_ids}))

    srv = nova.create_server(name=name, flavor=flavor_id, ports=dest_port_ids,    # C5
                             block_device_mapping=dest_vol_ids, availability_zone=az,
                             security_groups=sgs, key_name=keypair, metadata=metadata)
    results.append(StepResult("C5", ok=True, checkpoint={"destServerId": srv["id"]}))
    return results
