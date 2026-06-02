from app.engine.base import StepResult
from app.config import settings


def cutover(src_nova, src_cinder, dst_nova, dst_cinder, *, server_id, volume_ids,
            dest_port_ids, flavor_id, az, volume_type, sgs, keypair, metadata, name,
            root_volume_id, image_meta):
    """Generator: yields each StepResult as soon as its operation completes, so a
    mid-cutover failure leaves accurate checkpoints for rollback (no stranded state).

    Source clients (src_*) do C1 stop / C2 detach / C3 unmanage on the source cloud.
    Destination clients (dst_*) do C4 manage / C5 create on the destination cloud.
    On a shared backend the same physical array backs both, so the volume unmanaged
    from source becomes manageable on the destination."""
    src_nova.stop(server_id)                                             # C1
    yield StepResult("C1", ok=True, checkpoint={"wasRunning": True})

    for vid in volume_ids:                                               # C2
        src_nova.detach_volume(server_id, vid)
    yield StepResult("C2", ok=True, checkpoint={"detached": list(volume_ids)})

    unmanaged = [src_cinder.unmanage(vid) for vid in volume_ids]         # C3
    yield StepResult("C3", ok=True, checkpoint={"unmanaged": unmanaged})

    pool = dst_cinder.resolve_pool()                                     # C4
    dest_vol_ids = []
    for vid, backend_name in zip(volume_ids, unmanaged):
        ref = dst_cinder.wait_for_manageable(pool, backend_name,
                                             attempts=settings.manageable_poll_attempts,
                                             delay=0)
        new = dst_cinder.manage(host=pool, ref=ref, name=vid, volume_type=volume_type,
                                bootable=(vid == root_volume_id), az=az)
        if vid == root_volume_id:
            dst_cinder.set_image_metadata(new["id"], image_meta)
        dest_vol_ids.append(new["id"])
    yield StepResult("C4", ok=True, checkpoint={"destVolIds": dest_vol_ids})

    srv = dst_nova.create_server(name=name, flavor=flavor_id, ports=dest_port_ids,    # C5
                                 block_device_mapping=dest_vol_ids, availability_zone=az,
                                 security_groups=sgs, key_name=keypair, metadata=metadata)
    yield StepResult("C5", ok=True, checkpoint={"destServerId": srv["id"]})
