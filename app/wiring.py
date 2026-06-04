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
        source_conn_factory=source_conn,
        # runner_factory: LIVE-VALIDATE — assembling the execution ProductionEngine
        # (dest-scoped cinderclient, flavor/volume-type/pool resolution) requires two
        # shared-backend clouds to exercise. See LIVE_VALIDATION.md. Until wired, launches
        # store the Migration CR but do not execute.
        runner_factory=None)

    set_repos(destinations=destinations, migrations=migrations, discovery=discovery)
