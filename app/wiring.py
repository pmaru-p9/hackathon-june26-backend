"""Production-only: build real kubernetes + openstack clients and inject via set_repos.
Imported guardedly (only when PCD_MIGRATION_PROD=1) so unit tests never touch a cluster."""


def wire_production():
    from kubernetes import client, config

    from app.config import settings
    from app.deps import set_repos
    from app.store.adapters import K8sCustomObjectsAdapter, K8sSecretsAdapter
    from app.store.destinations import DestinationRepo
    from app.store.migrations import MigrationRepo

    config.load_incluster_config()
    co = K8sCustomObjectsAdapter(client.CustomObjectsApi())
    core = K8sSecretsAdapter(client.CoreV1Api())

    destinations = DestinationRepo(co, core, namespace=settings.namespace)
    migrations = MigrationRepo(co, core, namespace=settings.namespace)
    set_repos(destinations=destinations, migrations=migrations)
