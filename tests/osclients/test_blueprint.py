from app.osclients.blueprint import (
    parse_nfs_backends, export_for_pool, dest_pool_for_export)

# Synthetic blueprints — exercise the parse/match logic, not any real environment.
SRC_BP = [{"storageBackends": {"catA": {"bk": {"config": {"nfs_mount_points": "srv:/shared"}}}}}]
DST_BP = [{"storageBackends": {
    "catA": {"bk": {"config": {"nfs_mount_points": "srv:/other"}}},
    "catB": {"bk": {"config": {"nfs_mount_points": "srv:/shared"}}}}}]


def test_parse_and_export_for_pool():
    nb = parse_nfs_backends(SRC_BP)
    assert nb == {("catA", "bk"): "srv:/shared"}
    # pool host "uuid@bk#catA" -> matches by pool segment == category
    assert export_for_pool(nb, "uuid@bk#catA") == "srv:/shared"


def test_dest_pool_for_export_picks_matching_export():
    dst = parse_nfs_backends(DST_BP)
    pools = ["u1@bk#catA", "u2@bk#catB"]   # catA=srv:/other, catB=srv:/shared
    assert dest_pool_for_export(dst, pools, "srv:/shared") == "u2@bk#catB"
    assert dest_pool_for_export(dst, pools, "srv:/nope") is None
