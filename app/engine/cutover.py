from app.engine.base import StepResult
from app.config import settings


def cutover(src_nova, src_cinder, dst_nova, dst_cinder, *, server_id, volume_ids,
            root_volume_id, dest_pool_host, dest_port_ids, flavor_id, az, volume_type,
            sgs, keypair, metadata, name, image_meta, user_data=None, config_drive=False):
    """Boot-from-volume cutover. The root volume is freed by deleting the source instance
    (Nova won't detach a root device volume); delete_on_termination is read, temporarily
    set False if needed, and reapplied on the destination VM. Generator: yields each
    StepResult as it completes so failures leave accurate checkpoints."""
    src_nova.stop(server_id)                                              # C1
    yield StepResult("C1", ok=True, checkpoint={"wasRunning": True})

    data_volumes = [v for v in volume_ids if v != root_volume_id]         # C2
    for v in data_volumes:
        src_nova.detach_volume(server_id, v)
    yield StepResult("C2", ok=True, checkpoint={"detachedData": data_volumes})

    dot_original = src_nova.dot(server_id, root_volume_id)                 # C2b
    flipped = False
    if dot_original:
        src_nova.set_dot(server_id, root_volume_id, False)
        flipped = True
    yield StepResult("C2b", ok=True,
                     checkpoint={"dotOriginal": dot_original, "flipped": flipped})

    src_nova.delete(server_id)                                            # C2c
    # The root volume detaches asynchronously after the instance is deleted; wait until it
    # is 'available' or Cinder rejects the unmanage in C3.
    for v in volume_ids:
        src_cinder.wait_available(v, attempts=settings.manageable_poll_attempts,
                                  delay=settings.manageable_poll_seconds)
    yield StepResult("C2c", ok=True, checkpoint={"sourceDeleted": True})

    unmanaged = [src_cinder.unmanage(v) for v in volume_ids]              # C3
    yield StepResult("C3", ok=True, checkpoint={"unmanaged": unmanaged})

    dest_vol_ids = []                                                     # C4
    root_dest = None
    for vid, backend_name in zip(volume_ids, unmanaged):
        # NFS-family drivers don't populate list_manageable and need the full share-path
        # source-name; block drivers fall back to polling list_manageable.
        ref = dst_cinder.resolve_manage_ref(
            dest_pool_host, backend_name, attempts=settings.manageable_poll_attempts,
            delay=settings.manageable_poll_seconds)
        # volume_type left None: the host (pool) pins placement on the shared backend;
        # passing the resolved-pool marker as a type would be an invalid type name.
        new = dst_cinder.manage(host=dest_pool_host, ref=ref, name=vid,
                                volume_type=None, bootable=(vid == root_volume_id), az=az)
        # manage is async (NetApp: 'managing' -> 'available'); the volume cannot be booted
        # or unmanaged until it settles, so wait before C5.
        dst_cinder.wait_available(new["id"], attempts=settings.manageable_poll_attempts,
                                  delay=settings.manageable_poll_seconds)
        if vid == root_volume_id:
            dst_cinder.set_image_metadata(new["id"], image_meta)
            root_dest = new["id"]
        dest_vol_ids.append(new["id"])
    yield StepResult("C4", ok=True,
                     checkpoint={"destVolIds": dest_vol_ids, "rootDestVolId": root_dest})

    srv = dst_nova.create_server(name=name, flavor=flavor_id, ports=dest_port_ids,    # C5
                                 block_device_mapping=dest_vol_ids, root_volume_id=root_dest,
                                 root_delete_on_termination=dot_original,
                                 availability_zone=az, security_groups=sgs, key_name=keypair,
                                 metadata=metadata, user_data=user_data,
                                 config_drive=config_drive)
    yield StepResult("C5", ok=True, checkpoint={"destServerId": srv["id"]})
