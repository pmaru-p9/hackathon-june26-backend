class DiscoveryService:
    """Destination discovery + source introspection + runner assembly.

    Factories (injected by wire_production):
      conn_factory(destination_id)            -> DiscoveryConn  (dest, service acct)
      draft_conn_factory(creds_dict)          -> DiscoveryConn  (unsaved creds)
      source_conn_factory(url, token, proj)   -> SourceConn     (source, user token)
      runner_factory(migration_id)            -> MigrationRunner bound to a ProductionEngine
    """

    def __init__(self, conn_factory, draft_conn_factory=None, source_conn_factory=None,
                 runner_factory=None, shared_resolver=None):
        self.conn_factory = conn_factory
        self.draft_conn_factory = draft_conn_factory
        self.source_conn_factory = source_conn_factory
        self.runner_factory = runner_factory
        # shared_resolver(launch_body, tok) -> {sharedBackend, resolvedVolumeType,
        # destPoolHost, isAdmin} via blueprint NFS-export matching (set by wire_production).
        self.shared_resolver = shared_resolver

    # ---- destination connectivity / discovery -------------------------------------
    def test(self, did):
        try:
            self.conn_factory(did).authorize()
            return (True, "ok")
        except Exception as exc:  # noqa: BLE001
            return (False, str(exc))

    def test_draft(self, creds: dict):
        try:
            self.draft_conn_factory(creds).authorize()
            return (True, "ok")
        except Exception as exc:  # noqa: BLE001
            return (False, str(exc))

    def projects(self, did):
        return self.conn_factory(did).projects()

    def azs(self, did):
        return self.conn_factory(did).azs()

    def networks(self, did):
        return self.conn_factory(did).networks()

    def flavors(self, did):
        return self.conn_factory(did).flavors()

    # ---- source introspection -----------------------------------------------------
    def source_conn(self, auth_url, token, project_id):
        return self.source_conn_factory(auth_url, token, project_id)

    # ---- preflight assessment -----------------------------------------------------
    def assess(self, launch_body: dict, auth_url: str, token: str, project_id: str) -> dict:
        """Gather source + destination facts and score them into the preflight profile.

        SAFE-BY-DEFAULT: facts that require live, driver-specific verification
        (shared-backend confirmation, destination volume-type resolution, quota, admin
        role) default to the BLOCKING value so preflight FAILS until they are properly
        implemented and validated against two live clouds. See LIVE_VALIDATION.md."""
        from app.osclients.profile import build_migration_profile
        from app.osclients.assess import score_profile
        from app.osclients.nova import match_flavor

        sc = self.source_conn(auth_url, token, project_id)
        profile = build_migration_profile(sc, launch_body["vmIds"][0])

        disc = self.conn_factory(launch_body["destinationId"])
        try:
            disc.authorize()
            dest_reachable = True
        except Exception:  # noqa: BLE001
            dest_reachable = False

        networks = disc.networks() if dest_reachable else []
        dest_subnets = [{"network_id": n["id"], "cidr": s["cidr"], "allocated": []}
                        for n in networks for s in n.get("subnets", [])]
        network_map = {nm["sourcePortId"]: nm["destNetworkId"]
                       for nm in launch_body.get("networkMap", [])}

        specs = profile.get("flavorSpecs") or {}
        has_specs = all(specs.get(k) is not None for k in ("vcpus", "ram", "disk"))
        flavors = disc.flavors() if dest_reachable else []
        flavor_match = bool(launch_body.get("flavor", {}).get("overrideId")) or (
            has_specs and match_flavor(flavors, **specs) is not None)

        # Shared-backend / volume-type / admin resolved live via blueprint NFS-export match
        # (injected). Defaults stay BLOCKING if no resolver is wired.
        sb = {"sharedBackend": False, "resolvedVolumeType": None, "isAdmin": False}
        if self.shared_resolver:
            sb.update(self.shared_resolver(launch_body,
                                           {"token": token, "authUrl": auth_url,
                                            "projectId": project_id}))
        # TODO(live): volumes_detachable / quota_ok still defaulted True (LIVE_VALIDATION.md).
        return score_profile(
            profile, network_map, dest_subnets, dest_macs_in_use=[],
            is_admin=sb["isAdmin"], dest_reachable=dest_reachable,
            shared_backend=sb["sharedBackend"], resolved_volume_type=sb["resolvedVolumeType"],
            flavor_match=flavor_match, volumes_detachable=True, quota_ok=True)

    def resolve_backend(self, launch_body, auth_url, token, project_id):
        """Full shared-backend resolution incl. destPoolHost (for the runner's plan)."""
        if not self.shared_resolver:
            return {"sharedBackend": False, "destPoolHost": None, "resolvedVolumeType": None}
        return self.shared_resolver(launch_body,
                                    {"token": token, "authUrl": auth_url,
                                     "projectId": project_id})

    # ---- execution ----------------------------------------------------------------
    def runner_for(self, migration_id: str):
        if not self.runner_factory:
            return None
        return self.runner_factory(migration_id)
