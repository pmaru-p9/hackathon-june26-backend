"""Production-only: build real kubernetes + openstack clients and inject via set_repos.
Imported guardedly (only when PCD_MIGRATION_PROD=1) so unit tests never touch a cluster."""


def wire_production():
    from kubernetes import client, config

    from app.config import settings
    from app.deps import set_repos
    from app.store.adapters import K8sCustomObjectsAdapter, K8sSecretsAdapter
    from app.store.destinations import DestinationRepo
    from app.store.migrations import MigrationRepo
    from app.osclients import connections
    from app.osclients.discovery import DiscoveryService

    config.load_incluster_config()
    co = K8sCustomObjectsAdapter(client.CustomObjectsApi())
    core = K8sSecretsAdapter(client.CoreV1Api())

    destinations = DestinationRepo(co, core, namespace=settings.namespace)
    migrations = MigrationRepo(co, core, namespace=settings.namespace)

    def dest_conn(did):
        d = destinations.get(did)["spec"]
        creds = destinations.creds(did)
        conn = connections.dest_connection(
            auth_url=d["authUrl"], username=creds["username"], password=creds["password"],
            project_name=creds["project_name"], user_domain=creds["user_domain"],
            project_domain=creds["project_domain"], region_name=d.get("region"))
        return connections.DiscoveryConn(conn)

    def draft_conn(creds):
        conn = connections.dest_connection(
            auth_url=creds["authUrl"], username=creds["username"], password=creds["password"],
            project_name=creds["projectName"], user_domain=creds.get("userDomain", "Default"),
            project_domain=creds.get("projectDomain", "Default"))
        return connections.DiscoveryConn(conn)

    def source_conn(auth_url, token, project_id):
        return connections.SourceConn(
            connections.source_connection(auth_url, token, project_id))

    discovery = DiscoveryService(
        conn_factory=dest_conn, draft_conn_factory=draft_conn,
        source_conn_factory=source_conn, runner_factory=None)  # set below

    # --- execution wiring (runner_factory) ----------------------------------------
    from app.osclients.nova import NovaOps
    from app.osclients.cinder import CinderOps
    from app.osclients.neutron import NeutronOps
    from app.osclients.prod_clients import ProdNova, ProdCinder, ProdNeutron
    from app.engine.assembly import assemble_runner

    def build_source_clients(tok):
        conn = connections.source_connection(tok["authUrl"], tok["token"], tok["projectId"])
        return NovaOps(ProdNova(conn)), CinderOps(ProdCinder(connections.cinder_client(conn)))

    def build_dest_clients(did, target_project):
        d = destinations.get(did)["spec"]
        creds = destinations.creds(did)
        conn = connections.dest_connection_project(
            auth_url=d["authUrl"], username=creds["username"], password=creds["password"],
            project_id=target_project, user_domain=creds["user_domain"],
            region_name=d.get("region"))
        nova = NovaOps(ProdNova(conn))
        neutron = NeutronOps(ProdNeutron(conn))
        cinder = CinderOps(ProdCinder(connections.cinder_client(conn)))
        # LIVE-VALIDATE: resolve the dest cinder pool host + the volume type bound to the
        # shared backend before cutover. Left None here; preflight blocks until assess's
        # shared_backend/volume_type facts are implemented (LIVE_VALIDATION.md).
        return nova, cinder, neutron, None, None

    class _LazyRunner:
        """Defer the live assembly (source profile + assess) to the background task so the
        launch HTTP response isn't blocked on OpenStack calls."""
        def __init__(self, mid):
            self._mid = mid

        def run(self, mid):
            assemble_runner(mid, migrations=migrations, discovery=discovery,
                            build_source_clients=build_source_clients,
                            build_dest_clients=build_dest_clients).run(mid)

    discovery.runner_factory = lambda mid: _LazyRunner(mid)

    # --- shared-backend resolver (blueprint NFS-export match) ----------------------
    from app.osclients import blueprint
    from app.osclients.shared import resolve_shared
    from app.osclients.profile import build_migration_profile

    def _is_admin(conn):
        try:
            ref = conn.session.auth.get_auth_ref(conn.session)
            return "admin" in (ref.role_names or [])
        except Exception:  # noqa: BLE001
            return False

    def _base(auth_url):
        return auth_url.rsplit("/keystone", 1)[0]

    def shared_resolver(launch_body, tok):
        sconn = connections.source_connection(tok["authUrl"], tok["token"], tok["projectId"])
        scin = ProdCinder(connections.cinder_client(sconn))
        profile = build_migration_profile(connections.SourceConn(sconn), launch_body["vmIds"][0])
        src_bp = blueprint.fetch_blueprint(_base(tok["authUrl"]), tok["token"])

        d = destinations.get(launch_body["destinationId"])["spec"]
        creds = destinations.creds(launch_body["destinationId"])
        dconn = connections.dest_connection_project(
            auth_url=d["authUrl"], username=creds["username"], password=creds["password"],
            project_id=launch_body["targetProject"], user_domain=creds["user_domain"],
            region_name=d.get("region"))
        dcin = ProdCinder(connections.cinder_client(dconn))
        dst_bp = blueprint.fetch_blueprint(_base(d["authUrl"]), dconn.session.get_token())

        res = resolve_shared(source_cinder=scin, source_bp=src_bp, dest_cinder=dcin,
                             dest_bp=dst_bp, root_volume_id=profile["rootVolumeId"])
        res["isAdmin"] = _is_admin(sconn)
        return res

    discovery.shared_resolver = shared_resolver

    set_repos(destinations=destinations, migrations=migrations, discovery=discovery)
