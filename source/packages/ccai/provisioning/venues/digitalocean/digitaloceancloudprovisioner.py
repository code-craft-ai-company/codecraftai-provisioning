"""
    .. module:: digitaloceancloudprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: DigitalOceanCloudProvisioner — concrete CloudProvisioner for
               DigitalOcean.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import json
import os

from typing import Any, Dict, List, Optional

from ccai.credentials.digitaloceanapitokencredential import (
    DigitalOceanApiTokenCredential
)
from ccai.provisioning.model.cloud.cloudprovisioner import CloudProvisioner
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.model.cloud.provisioningplan import ProvisioningPlan
from ccai.provisioning.model.cloud.provisioningresult import (
    ProvisioningResult
)
from ccai.provisioning.model.cloud.validationresult import ValidationResult
from ccai.provisioning.venues.vpncleanup import delete_vpn_device

from ccai.provisioning.venues.digitalocean.doclient import (
    DigitalOceanClient
)
from ccai.provisioning.venues.digitalocean.doerrors import (
    DoValidationError
)
from ccai.provisioning.venues.digitalocean.doregionconfig import (
    DoRegionConfig, KNOWN_DO_REGIONS
)
from ccai.provisioning.venues.digitalocean.doresolver import DoResolver
from ccai.provisioning.venues.digitalocean.dospec import DoSpec
from ccai.provisioning.venues.digitalocean.douserdatarenderer import (
    DoUserDataRenderer
)
from ccai.provisioning.venues.digitalocean.resources.dnsmanager import (
    DnsManager
)
from ccai.provisioning.venues.digitalocean.resources.dropletmanager import (
    DropletManager
)
from ccai.provisioning.venues.digitalocean.resources.firewallmanager import (
    FirewallManager
)
from ccai.provisioning.venues.digitalocean.resources.networkmanager import (
    NetworkManager
)
from ccai.provisioning.venues.digitalocean.resources.spacesmanager import (
    SpacesManager
)
from ccai.provisioning.venues.digitalocean.resources.sshkeymanager import (
    SshKeyManager
)
from ccai.provisioning.venues.digitalocean.resources.volumemanager import (
    VolumeManager
)


# Shared-FS kinds DigitalOcean cannot realise natively.
_UNSUPPORTED_FS_KINDS = frozenset({"LUSTRE", "WEKA", "VAST", "GPFS",
                                   "BEEGFS", "VENUE_NATIVE"})

# Interconnect kinds DigitalOcean has no product for.
_REJECTED_INTERCONNECTS = frozenset({"INFINIBAND_HDR", "INFINIBAND_NDR",
                                     "INFINIBAND_XDR", "EFA", "OCI_RDMA",
                                     "ROCE"})


class DigitalOceanCloudProvisioner(CloudProvisioner):
    """
        DigitalOcean-venue concrete :class:`CloudProvisioner` implementation.

        Composes the per-resource managers behind the five-verb lifecycle.
        DigitalOcean is intentionally lower-feature than the hyperscalers:
        the provisioner is honest in ``validate`` about which neutral asks
        (HPC interconnect, WEKA/Lustre-class shared FS) have no DigitalOcean
        realisation and rejects them with substitution guidance.
    """

    VENUE_NAME: str = "digitalocean"

    def __init__(self, *, venue: CloudVenue,
                 credential: DigitalOceanApiTokenCredential,
                 region_config: DoRegionConfig,
                 spec: Optional[DoSpec] = None,
                 client: Optional[DigitalOceanClient] = None,
                 vpn_control_plane: Optional[Any] = None,
                 output_root: Optional[str] = None) -> None:
        """
            Construct a DigitalOceanCloudProvisioner.

            :param venue: CloudVenue.
            :param credential: DigitalOceanApiTokenCredential.
            :param region_config: DoRegionConfig.
            :param spec: Optional DoSpec.
            :param client: Optional pre-built DigitalOceanClient (tests
                           inject a mock-backed client).
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl;
                                      destroy uses this to de-register
                                      Tailscale / Twingate devices.
            :param output_root: Optional root directory for inventory
                                persistence (defaults to ``.output``).
        """
        super().__init__(venue=venue, spec=spec)
        self._credential: DigitalOceanApiTokenCredential = credential
        self._region_config: DoRegionConfig = region_config

        if client is not None:
            self._client: DigitalOceanClient = client
        else:
            self._client = DigitalOceanClient(credential=credential)

        self._vpn_control_plane: Optional[Any] = vpn_control_plane
        self._output_root: str = output_root if output_root is not None else ".output"

        self._resolver: DoResolver = DoResolver()
        self._user_data_renderer: DoUserDataRenderer = DoUserDataRenderer()

        self._network_mgr: NetworkManager = NetworkManager(
            client=self._client
        )
        self._firewall_mgr: FirewallManager = FirewallManager(
            client=self._client
        )
        self._sshkey_mgr: SshKeyManager = SshKeyManager(client=self._client)
        self._droplet_mgr: DropletManager = DropletManager(
            client=self._client, resolver=self._resolver,
            user_data_renderer=self._user_data_renderer,
        )
        self._volume_mgr: VolumeManager = VolumeManager(client=self._client)
        self._spaces_mgr: SpacesManager = SpacesManager(client=self._client)
        self._dns_mgr: DnsManager = DnsManager(client=self._client)

        self._last_run_id: Optional[str] = None
        self._last_vpn_records: List[Dict[str, Any]] = []
        return

    # ------------------------------------------------------------------
    # Lifecycle: validate
    # ------------------------------------------------------------------

    def validate(self, *, aspects: Any = None) -> ValidationResult:
        """
            Validate the DoSpec without any DigitalOcean API calls.

            :param aspects: Aspects (or compatible).

            :returns: A ValidationResult with ok=True on success.
            :raises: DoValidationError
        """
        if not isinstance(self._credential, DigitalOceanApiTokenCredential):
            err_msg_lines = [
                "DigitalOceanCloudProvisioner requires a "
                "DigitalOceanApiTokenCredential."
            ]
            err_msg_lines.append("ACTUAL: {}".format(
                type(self._credential).__name__
            ))
            err_msg = os.linesep.join(err_msg_lines)
            raise DoValidationError(err_msg)

        spec = self._spec
        if spec is None:
            rtnval = ValidationResult(ok=True)
            return rtnval

        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []

        # Shared FS kinds — DigitalOcean has no WEKA/Lustre-class product.
        for sfs in spec.shared_filesystems:
            if sfs.kind in _UNSUPPORTED_FS_KINDS:
                errors.append({
                    "resource": sfs.name,
                    "error": ("DigitalOcean offers no native shared-FS "
                              "equivalent of kind {}; the only supported "
                              "path is attach-existing self-hosted NFS "
                              "realised as a Droplet sized for the role "
                              "(set existing_id).").format(sfs.kind),
                })
            else:
                if sfs.existing_id is None or len(sfs.existing_id) == 0:
                    errors.append({
                        "resource": sfs.name,
                        "error": ("DigitalOcean shared-FS support is "
                                  "attach-existing only; set existing_id."),
                    })

        # Per-instance: interconnect rejection + size/image resolution.
        for instance in spec.instances:
            if instance.interconnect is not None:
                ic_kind = instance.interconnect.kind
                if ic_kind != "NONE" and ic_kind in _REJECTED_INTERCONNECTS:
                    errors.append({
                        "resource": instance.name,
                        "error": ("DigitalOcean has no HPC cluster "
                                  "interconnect product; remove the "
                                  "CloudInterconnect (kind={}) or move the "
                                  "workload to a hyperscaler venue.").format(
                                      ic_kind
                                  ),
                    })
                elif ic_kind not in ("NONE", "ETHERNET"):
                    errors.append({
                        "resource": instance.name,
                        "error": ("DigitalOcean only provides standard "
                                  "Ethernet networking; got "
                                  "interconnect kind {}.").format(ic_kind),
                    })

            # Image slug resolution.
            try:
                self._resolver.image_to_slug(
                    family=instance.image.family,
                    version=instance.image.version,
                    architecture=instance.image.architecture,
                )
            except DoValidationError as xcpt:
                errors.append({"resource": instance.name,
                               "error": str(xcpt)})

            # Size / GPU slug resolution.
            try:
                self._resolver.size_to_slug(
                    size_hint=instance.size,
                    accelerators=instance.accelerators,
                )
            except DoValidationError as xcpt:
                errors.append({"resource": instance.name,
                               "error": str(xcpt)})

        # Droplet / network region slugs.
        for net in spec.networks:
            if net.region not in KNOWN_DO_REGIONS:
                errors.append({
                    "resource": net.name,
                    "error": ("Unknown DigitalOcean region slug: "
                              "{}.").format(net.region),
                })

        if self._region_config.region not in KNOWN_DO_REGIONS:
            errors.append({
                "resource": "<region-config>",
                "error": ("Unknown DigitalOcean region slug: "
                          "{}.").format(self._region_config.region),
            })

        # Tag encoding round-trip check on every declared resource.
        for entry in self._all_tags_of(spec=spec):
            for key, value in entry.items():
                tag_string = "{}={}".format(key, value)
                if len(tag_string) > 255:
                    errors.append({
                        "resource": "<tags>",
                        "error": ("Encoded tag exceeds 255 chars: "
                                  "key={}.").format(key),
                    })

        # Load balancers are accepted for v1.5 stubbing with a warning.
        for lb in spec.load_balancers:
            warnings.append({
                "resource": lb.name,
                "warning": ("CloudLoadBalancer apply is a v1.5 stub on the "
                            "DigitalOcean venue; not yet implemented."),
            })

        if len(errors) > 0:
            err_msg_lines = [
                "DigitalOceanCloudProvisioner.validate found errors."
            ]
            for entry in errors:
                err_msg_lines.append("    {}: {}".format(
                    entry["resource"], entry["error"]
                ))
            err_msg = os.linesep.join(err_msg_lines)
            raise DoValidationError(err_msg)

        rtnval = ValidationResult(ok=True, warnings=warnings)
        return rtnval

    @staticmethod
    def _all_tags_of(*, spec: DoSpec) -> List[Dict[str, str]]:
        """
            Flatten every tag dict declared anywhere in a DoSpec.

            :param spec: The DoSpec.

            :returns: A list of single-entry tag dicts.
        """
        out: List[Dict[str, str]] = []
        for collection in (spec.networks, spec.security_groups,
                           spec.instances, spec.volumes, spec.buckets):
            for entry in collection:
                tags = getattr(entry, "tags", None)
                if tags is not None:
                    for tag in tags:
                        out.append(tag)
        rtnval = out
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: plan
    # ------------------------------------------------------------------

    def plan(self, *, aspects: Any = None) -> ProvisioningPlan:
        """
            Compute a CREATE/SKIP/UPDATE/DELETE plan.

            Performs read-only reads; no mutation.

            :param aspects: Aspects.

            :returns: A ProvisioningPlan.
        """
        run_id = self._run_id(aspects=aspects)
        spec = self._spec
        actions = []

        if spec is None:
            rtnval = ProvisioningPlan(actions=actions)
            return rtnval

        # Networks (VPCs).
        for net in spec.networks:
            existing = self._network_mgr.find(run_id=run_id, name=net.name)
            if existing is None:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="network", resource_name=net.name,
                ))
            elif self._network_mgr.matches(existing=existing, desired=net):
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="network", resource_name=net.name,
                ))
            else:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.UPDATE,
                    resource_kind="network", resource_name=net.name,
                    diff={"before": {"cidr": existing.get("ip_range", "")},
                          "after": {"cidr": net.cidr}},
                ))

        # Firewalls.
        for group in spec.security_groups:
            existing = self._firewall_mgr.find(run_id=run_id,
                                               name=group.name)
            if existing is None:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="sg", resource_name=group.name,
                ))
            elif self._firewall_mgr.matches(existing=existing,
                                            desired=group):
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="sg", resource_name=group.name,
                ))
            else:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.UPDATE,
                    resource_kind="sg", resource_name=group.name,
                ))

        # SSH keys.
        for kp in spec.keypairs:
            existing = self._sshkey_mgr.find(run_id=run_id, name=kp.name,
                                             desired=kp)
            if existing is None:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="keypair", resource_name=kp.name,
                ))
            else:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="keypair", resource_name=kp.name,
                ))

        # Droplets.
        for inst in spec.instances:
            existing = self._droplet_mgr.find(run_id=run_id, name=inst.name)
            if existing is None:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="instance", resource_name=inst.name,
                ))
            elif self._droplet_mgr.matches(existing=existing, desired=inst):
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="instance", resource_name=inst.name,
                ))
            else:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.UPDATE,
                    resource_kind="instance", resource_name=inst.name,
                    diff={"note": "Droplet size change is "
                                  "UPDATE-by-recreate."},
                ))

        # Volumes.
        for vol in spec.volumes:
            existing = self._volume_mgr.find(run_id=run_id, name=vol.name)
            if existing is None:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="volume", resource_name=vol.name,
                ))
            else:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="volume", resource_name=vol.name,
                ))

        # Buckets (Spaces).
        for bucket in spec.buckets:
            exists = self._spaces_mgr.find(
                run_id=run_id, name=bucket.name,
                region=self._region_config.spaces_region,
            )
            if exists is not True:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="bucket", resource_name=bucket.name,
                ))
            else:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="bucket", resource_name=bucket.name,
                ))

        # DNS records.
        for record in spec.dns_records:
            existing_dns = self._dns_mgr._existing_record(
                zone=record.zone, name=record.name,
                record_type=record.record_type,
            )
            if existing_dns is None:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="dns", resource_name=record.name,
                ))
            else:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="dns", resource_name=record.name,
                ))

        # Load balancers — emit-skip until v1.5.
        for lb in spec.load_balancers:
            actions.append(self._planned_action_for(
                intent=PlannedActionIntent.SKIP,
                resource_kind="lb", resource_name=lb.name,
                diff={"note": "Load balancer apply is deferred to v1.5."},
            ))

        rtnval = ProvisioningPlan(actions=actions)
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: apply
    # ------------------------------------------------------------------

    def apply(self, *, aspects: Any = None) -> ProvisioningResult:
        """
            Apply the spec idempotently.

            Stages: VPC -> firewall -> SSH key -> Droplet -> volume ->
            Spaces -> DNS.

            :param aspects: Aspects.

            :returns: A ProvisioningResult.
        """
        if self._spec is None:
            rtnval = ProvisioningResult()
            return rtnval

        run_id = self._run_id(aspects=aspects)
        self._last_run_id = run_id
        default_tags = self._region_config.default_tags
        region = self._region_config.region
        spec = self._spec

        created: List[ProvisionedResource] = []
        updated: List[ProvisionedResource] = []
        skipped: List[str] = []
        vpn_records: List[Dict[str, Any]] = []

        # --- VPCs ---
        network_state: Dict[str, ProvisionedResource] = {}
        for net in spec.networks:
            existed = self._network_mgr.find(
                run_id=run_id, name=net.name
            ) is not None
            resource = self._network_mgr.ensure(
                desired=net, run_id=run_id, region=region,
                default_tags=default_tags, aspects=aspects,
            )
            network_state[net.name] = resource
            if existed:
                skipped.append(net.name)
            else:
                created.append(resource)

        # --- firewalls ---
        for group in spec.security_groups:
            existed = self._firewall_mgr.find(
                run_id=run_id, name=group.name
            ) is not None
            resource = self._firewall_mgr.ensure(
                desired=group, run_id=run_id, default_tags=default_tags,
                aspects=aspects,
            )
            if existed:
                skipped.append(group.name)
            else:
                created.append(resource)

        # --- SSH keys ---
        kp_state: Dict[str, ProvisionedResource] = {}
        for kp in spec.keypairs:
            existed = self._sshkey_mgr.find(
                run_id=run_id, name=kp.name, desired=kp
            ) is not None
            resource = self._sshkey_mgr.ensure(
                desired=kp, run_id=run_id, aspects=aspects,
            )
            kp_state[kp.name] = resource
            if existed:
                skipped.append(kp.name)
            else:
                created.append(resource)

        # --- Droplets ---
        instance_state: Dict[str, ProvisionedResource] = {}
        for inst in spec.instances:
            vpc_uuid = ""
            subnet_name = inst.subnet
            for net in spec.networks:
                if net.name == subnet_name:
                    parent = network_state.get(net.name, None)
                    if parent is not None:
                        vpc_uuid = str(parent.attributes.get("vpc_id", ""))
            # Subnets fold into the VPC; allow subnet to name a network.
            parent = network_state.get(subnet_name, None)
            if parent is not None:
                vpc_uuid = str(parent.attributes.get("vpc_id", ""))

            ssh_key_ids: List[Any] = []
            if inst.keypair is not None:
                kp_res = kp_state.get(inst.keypair, None)
                if kp_res is not None:
                    ssh_key_ids.append(kp_res.attributes.get("ssh_key_id"))

            authkey: Optional[str] = None
            if inst.vpn_join is not None and self._vpn_control_plane is not None:
                authkey = getattr(self._vpn_control_plane,
                                  "minted_authkey", None)

            existed = self._droplet_mgr.find(
                run_id=run_id, name=inst.name
            ) is not None
            resource, info = self._droplet_mgr.ensure(
                desired=inst, run_id=run_id, region=region,
                vpc_uuid=vpc_uuid, ssh_key_ids=ssh_key_ids,
                default_tags=default_tags, authkey=authkey,
                aspects=aspects,
            )
            instance_state[inst.name] = resource
            if existed:
                skipped.append(inst.name)
            else:
                created.append(resource)
                if inst.vpn_join is not None:
                    vpn_records.append({
                        "instance_name": inst.name,
                        "droplet_id": resource.attributes.get("droplet_id",
                                                              ""),
                        "vpn_provider": inst.vpn_join.provider,
                        "vpn_device_id": info.get("vpn_device_id", None),
                    })

        # --- volumes ---
        for vol in spec.volumes:
            attach_id = None
            if vol.attached_to is not None:
                target = instance_state.get(vol.attached_to, None)
                if target is not None:
                    attach_id = target.attributes.get("droplet_id", None)

            existed = self._volume_mgr.find(
                run_id=run_id, name=vol.name
            ) is not None
            resource = self._volume_mgr.ensure(
                desired=vol, run_id=run_id, region=region,
                default_tags=default_tags, attach_droplet_id=attach_id,
                aspects=aspects,
            )
            if existed:
                skipped.append(vol.name)
            else:
                created.append(resource)

        # --- Spaces ---
        for bucket in spec.buckets:
            existed = self._spaces_mgr.find(
                run_id=run_id, name=bucket.name,
                region=self._region_config.spaces_region,
            )
            resource = self._spaces_mgr.ensure(
                desired=bucket, run_id=run_id,
                region=self._region_config.spaces_region,
                default_tags=default_tags, aspects=aspects,
            )
            if existed is True:
                skipped.append(bucket.name)
            else:
                created.append(resource)

        # --- DNS ---
        for record in spec.dns_records:
            existed_dns = self._dns_mgr._existing_record(
                zone=record.zone, name=record.name,
                record_type=record.record_type,
            ) is not None
            resource = self._dns_mgr.ensure(
                desired=record, run_id=run_id, aspects=aspects,
            )
            if existed_dns:
                skipped.append(record.name)
            else:
                created.append(resource)

        self._last_vpn_records = vpn_records

        rtnval = ProvisioningResult(created=created, updated=updated,
                                    skipped=skipped, errors=[])
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: destroy
    # ------------------------------------------------------------------

    def _destroy_impl(self, *, aspects: Any) -> None:
        """
            Destroy every owned resource in reverse dependency order.

            :param aspects: Aspects.
        """
        run_id = self._run_id(aspects=aspects)
        spec = self._spec

        # 1. DNS records.
        if spec is not None:
            for record in spec.dns_records:
                self._dns_mgr.destroy_record(desired=record,
                                             aspects=aspects)

        # 2. Spaces buckets.
        if spec is not None:
            bucket_names = [b.name for b in spec.buckets]
            self._spaces_mgr.destroy(
                run_id=run_id, names=bucket_names,
                region=self._region_config.spaces_region, aspects=aspects,
            )

        # 3. Volumes.
        self._volume_mgr.destroy(run_id=run_id, aspects=aspects)

        # 4. Droplets — capture records for VPN cleanup.
        destroyed = self._droplet_mgr.destroy(run_id=run_id, aspects=aspects)

        # 5. VPN control-plane device cleanup.
        if self._vpn_control_plane is not None:
            for record in self._last_vpn_records:
                device_id = record.get("vpn_device_id", None)
                if device_id is None or len(str(device_id)) == 0:
                    continue
                delete_vpn_device(
                    vpn_control_plane=self._vpn_control_plane,
                    device_id=device_id, aspects=aspects)
            for record in destroyed:
                device_id = record.get("vpn_device_id", None)
                if device_id is None or len(str(device_id)) == 0:
                    continue
                delete_vpn_device(
                    vpn_control_plane=self._vpn_control_plane,
                    device_id=device_id, aspects=aspects)

        # 6. SSH keys.
        if spec is not None:
            key_names = [k.name for k in spec.keypairs]
            self._sshkey_mgr.destroy(run_id=run_id, names=key_names,
                                     aspects=aspects)

        # 7. Firewalls.
        self._firewall_mgr.destroy(run_id=run_id, aspects=aspects)

        # 8. VPCs.
        self._network_mgr.destroy(run_id=run_id, aspects=aspects)
        return

    # ------------------------------------------------------------------
    # Lifecycle: inventory
    # ------------------------------------------------------------------

    def inventory(self, *, aspects: Any = None) -> List[ProvisionedResource]:
        """
            Enumerate owned resources for the run.

            The inventory is also persisted under
            ``<output_root>/provisioning/<runid>/do-inventory.json``.

            :param aspects: Aspects.

            :returns: A list of ProvisionedResource entries.
        """
        run_id = self._run_id(aspects=aspects)
        out: List[ProvisionedResource] = []
        out.extend(self._network_mgr.list_owned(run_id=run_id))
        out.extend(self._firewall_mgr.list_owned(run_id=run_id))
        out.extend(self._droplet_mgr.list_owned(run_id=run_id))
        out.extend(self._volume_mgr.list_owned(run_id=run_id))

        if self._spec is not None:
            bucket_names = [b.name for b in self._spec.buckets]
            out.extend(self._spaces_mgr.list_owned(
                run_id=run_id, names=bucket_names,
                region=self._region_config.spaces_region,
            ))
            out.extend(self._dns_mgr.list_owned(
                dns_records=self._spec.dns_records
            ))

        self._persist_inventory(run_id=run_id, resources=out)

        rtnval = out
        return rtnval

    def _persist_inventory(self, *, run_id: str,
                           resources: List[ProvisionedResource]) -> None:
        """
            Persist the inventory to a run-scoped JSON file.

            :param run_id: Run identifier.
            :param resources: The inventory list.
        """
        out_dir = os.path.join(self._output_root, "provisioning", run_id)
        try:
            os.makedirs(out_dir, exist_ok=True)
        except OSError:
            return

        payload: List[Dict[str, Any]] = []
        for resource in resources:
            entry: Dict[str, Any] = {}
            entry["kind"] = resource.kind
            entry["name"] = resource.name
            entry["venue_id"] = resource.venue_id
            entry["attributes"] = dict(resource.attributes)
            entry["tags"] = dict(resource.tags)
            payload.append(entry)

        out_path = os.path.join(out_dir, "do-inventory.json")
        try:
            with open(out_path, "w", encoding="utf-8") as out_file:
                json.dump(payload, out_file, indent=2, sort_keys=True)
        except OSError:
            return
        return

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def record_vpn_device(self, *, instance_name: str,
                          device_id: str) -> None:
        """
            Record the VPN device id minted for an instance.

            :param instance_name: Neutral instance name.
            :param device_id: Provider-assigned device id.
        """
        for record in self._last_vpn_records:
            if record.get("instance_name", "") == instance_name:
                record["vpn_device_id"] = device_id
                return
        self._last_vpn_records.append({
            "instance_name": instance_name,
            "vpn_device_id": device_id,
        })
        return

    @property
    def last_vpn_records(self) -> List[Dict[str, Any]]:
        """
            Return the recorded VPN device records from the last apply.

            :returns: A defensive copy of the records.
        """
        rtnval = [dict(entry) for entry in self._last_vpn_records]
        return rtnval

    def _run_id(self, *, aspects: Any) -> str:
        """
            Resolve the run identifier from aspects or fall back to venue.

            :param aspects: Aspects.

            :returns: A non-empty run id string.
        """
        candidate = self._aspect_attr(aspects=aspects, name="runid",
                                      default=None)
        if candidate is not None and len(candidate) > 0:
            rtnval = candidate
            return rtnval
        rtnval = "do-{}".format(self._venue.name)
        return rtnval
