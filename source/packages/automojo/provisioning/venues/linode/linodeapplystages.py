"""
    .. module:: linodeapplystages
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LinodeApplyStages — idempotent create-or-reuse stages for the
               Linode venue (network/firewall, instances/volumes,
               object-storage/dns).

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.venues.linode.linodereader import LinodeReader
from automojo.provisioning.venues.linode.linoderegionconfig import (
    LinodeRegionConfig
)
from automojo.provisioning.venues.linode.linoderesolver import LinodeResolver
from automojo.provisioning.venues.linode.linodespec import LinodeSpec
from automojo.provisioning.venues.linode.linodetagtranslator import (
    LinodeTagTranslator
)
from automojo.provisioning.venues.linode.linodeuserdatarenderer import (
    LinodeUserDataRenderer
)


class LinodeApplyResult:
    """
        Mutable accumulator threaded through the apply stages.

        Tracks created, updated, and skipped resources plus the VPN device
        records produced during instance creation.
    """

    def __init__(self) -> None:
        """
            Construct an empty LinodeApplyResult.
        """
        self.created: List[ProvisionedResource] = []
        self.updated: List[ProvisionedResource] = []
        self.skipped: List[str] = []
        self.vpn_records: List[Dict[str, Any]] = []
        return


class LinodeApplyStages:
    """
        Idempotent apply stages for the Linode venue.

        Each stage performs read-before-create against the
        :class:`LinodeReader`; an existing owned resource is reused and
        recorded as skipped.  Stages run in dependency order:
        VPC → Firewall → SSH key → Instance → Volume → Object Storage → DNS.
    """

    def __init__(self, *, client: Any, reader: LinodeReader,
                 resolver: LinodeResolver,
                 translator: LinodeTagTranslator,
                 region_config: LinodeRegionConfig,
                 user_data_renderer: LinodeUserDataRenderer,
                 vpn_control_plane: Optional[Any] = None) -> None:
        """
            Construct a LinodeApplyStages.

            :param client: A ``linode_api4.LinodeClient``-compatible object.
            :param reader: A LinodeReader.
            :param resolver: A LinodeResolver.
            :param translator: A LinodeTagTranslator.
            :param region_config: A LinodeRegionConfig.
            :param user_data_renderer: A LinodeUserDataRenderer.
            :param vpn_control_plane: Optional IVPNControlPlane impl.
        """
        self._client: Any = client
        self._reader: LinodeReader = reader
        self._resolver: LinodeResolver = resolver
        self._translator: LinodeTagTranslator = translator
        self._region_config: LinodeRegionConfig = region_config
        self._user_data_renderer: LinodeUserDataRenderer = user_data_renderer
        self._vpn_control_plane: Optional[Any] = vpn_control_plane
        return

    def apply_network_and_firewall(self, *, spec: LinodeSpec, run_id: str,
                                   result: LinodeApplyResult,
                                   aspects: Any) -> Dict[str, Any]:
        """
            Apply VPCs, VPC subnets, Cloud Firewalls, and SSH keys.

            :param spec: The LinodeSpec.
            :param run_id: The run identifier.
            :param result: The LinodeApplyResult accumulator.
            :param aspects: Aspects.

            :returns: A state dict mapping resource kinds to created handles.
        """
        defaults = self._region_config.default_tags

        network_state: Dict[str, Any] = {}
        for net in spec.networks:
            existing = self._reader.find_vpc(name=net.name)
            if existing is not None:
                network_state[net.name] = existing
                result.skipped.append(net.name)
                continue
            tags = self._translator.owner_tags(
                run_id=run_id, resource_name=net.name,
                resource_kind="network", extra=list(net.tags),
                defaults=defaults,
            )
            created = self._client.vpc_create(
                label="automojo-{}-{}".format(run_id, net.name),
                region=net.region, tags=tags,
            )
            network_state[net.name] = created
            attributes: Dict[str, Any] = {}
            attributes["vpc_id"] = getattr(created, "id", "")
            attributes["region"] = net.region
            attributes["cidr"] = net.cidr
            result.created.append(ProvisionedResource(
                kind="network", name=net.name,
                venue_id=str(getattr(created, "id", "")),
                attributes=attributes,
                tags=self._translator.from_linode(strings=tags),
            ))

        subnet_state: Dict[str, Any] = {}
        for subnet in spec.subnets:
            existing = self._reader.find_subnet(name=subnet.name)
            if existing is not None:
                subnet_state[subnet.name] = existing
                result.skipped.append(subnet.name)
                continue
            parent = network_state.get(subnet.network, None)
            if parent is None:
                continue
            created = self._client.vpc_subnet_create(
                vpc=parent, label=subnet.name, ipv4=subnet.cidr,
            )
            subnet_state[subnet.name] = created
            attributes = {}
            attributes["subnet_id"] = getattr(created, "id", "")
            attributes["cidr"] = subnet.cidr
            result.created.append(ProvisionedResource(
                kind="subnet", name=subnet.name,
                venue_id=str(getattr(created, "id", "")),
                attributes=attributes, tags=[],
            ))

        firewall_state: Dict[str, Any] = {}
        for sg in spec.security_groups:
            existing = self._reader.find_firewall(name=sg.name)
            if existing is not None:
                firewall_state[sg.name] = existing
                result.skipped.append(sg.name)
                continue
            tags = self._translator.owner_tags(
                run_id=run_id, resource_name=sg.name,
                resource_kind="sg", extra=list(sg.tags),
                defaults=defaults,
            )
            rules = self._firewall_rules(sg=sg)
            created = self._client.firewall_create(
                label="automojo-{}-{}".format(run_id, sg.name),
                rules=rules, tags=tags,
            )
            firewall_state[sg.name] = created
            result.created.append(ProvisionedResource(
                kind="sg", name=sg.name,
                venue_id=str(getattr(created, "id", "")),
                attributes={"firewall_id": getattr(created, "id", "")},
                tags=self._translator.from_linode(strings=tags),
            ))

        keypair_state: Dict[str, Any] = {}
        for kp in spec.keypairs:
            existing = self._reader.find_sshkey(name=kp.name)
            if existing is not None:
                keypair_state[kp.name] = existing
                result.skipped.append(kp.name)
                continue
            created = self._client.profile.ssh_key_upload(
                key=kp.public_key_material,
                label="automojo-{}-{}".format(run_id, kp.name),
            )
            keypair_state[kp.name] = created
            result.created.append(ProvisionedResource(
                kind="keypair", name=kp.name,
                venue_id=str(getattr(created, "id", "")),
                attributes={"public_key": kp.public_key_material},
                tags=[],
            ))

        rtnval: Dict[str, Any] = {
            "networks": network_state,
            "subnets": subnet_state,
            "firewalls": firewall_state,
            "keypairs": keypair_state,
        }
        return rtnval

    def apply_instances_and_volumes(self, *, spec: LinodeSpec, run_id: str,
                                    state: Dict[str, Any],
                                    result: LinodeApplyResult,
                                    aspects: Any) -> Dict[str, Any]:
        """
            Apply Linode instances (with metadata user-data) and volumes.

            :param spec: The LinodeSpec.
            :param run_id: The run identifier.
            :param state: The state dict from apply_network_and_firewall.
            :param result: The LinodeApplyResult accumulator.
            :param aspects: Aspects.

            :returns: An instance-state dict for downstream stages.
        """
        defaults = self._region_config.default_tags
        firewall_state = state.get("firewalls", {})
        subnet_state = state.get("subnets", {})
        keypair_state = state.get("keypairs", {})

        instance_state: Dict[str, Any] = {}
        for inst in spec.instances:
            existing = self._reader.find_instance(name=inst.name)
            if existing is not None:
                instance_state[inst.name] = existing
                result.skipped.append(inst.name)
                continue

            accelerator_models = self._accelerator_models(instance=inst)
            type_slug = self._resolver.size_to_type(
                size_hint=inst.size, accelerators=accelerator_models,
            )
            image_id = self._resolver.image_to_id(
                family=inst.image.family, version=inst.image.version,
                architecture=inst.image.architecture,
            )

            authorized_keys: List[str] = []
            if inst.keypair is not None:
                kp_handle = keypair_state.get(inst.keypair, None)
                if kp_handle is not None:
                    key_material = getattr(kp_handle, "ssh_key", None)
                    if key_material is None:
                        key_material = getattr(kp_handle, "public_key", None)
                    if key_material is not None:
                        authorized_keys.append(key_material)

            metadata_user_data: Optional[str] = None
            vpn_device_id: Optional[str] = None
            if inst.vpn_join is not None:
                authkey = ""
                if self._vpn_control_plane is not None:
                    authkey = getattr(self._vpn_control_plane,
                                      "minted_authkey", "") or ""
                    vpn_device_id = getattr(self._vpn_control_plane,
                                            "minted_device_id", None)
                rendered_hostname = inst.vpn_join.hostname_template.format(
                    instance_name=inst.name
                )
                metadata_user_data = self._user_data_renderer.render(
                    spec=inst.vpn_join, authkey=authkey,
                    rendered_hostname=rendered_hostname,
                    image_family=inst.image.family,
                )
            elif inst.user_data_script is not None:
                metadata_user_data = self._user_data_renderer.render_raw(
                    user_data_script=inst.user_data_script
                )

            tags = self._translator.owner_tags(
                run_id=run_id, resource_name=inst.name,
                resource_kind="instance", extra=list(inst.tags),
                defaults=defaults,
            )

            firewall_id = None
            ref_sgs = inst.security_groups if inst.security_groups is not None else []
            for sg_name in ref_sgs:
                fw_handle = firewall_state.get(sg_name, None)
                if fw_handle is not None:
                    firewall_id = getattr(fw_handle, "id", None)
                    break

            metadata: Dict[str, Any] = {}
            if metadata_user_data is not None:
                metadata["user_data"] = metadata_user_data

            created = self._client.instance_create(
                ltype=type_slug, region=self._region_config.region,
                image=image_id,
                label="automojo-{}-{}".format(run_id, inst.name),
                tags=tags, authorized_keys=authorized_keys,
                metadata=metadata, firewall=firewall_id,
                private_ip=False,
            )
            instance_state[inst.name] = created

            attributes: Dict[str, Any] = {}
            attributes["instance_id"] = getattr(created, "id", "")
            attributes["type"] = type_slug
            attributes["image"] = image_id
            attributes["region"] = self._region_config.region
            if metadata_user_data is not None:
                attributes["metadata_user_data"] = metadata_user_data

            result.created.append(ProvisionedResource(
                kind="instance", name=inst.name,
                venue_id=str(getattr(created, "id", "")),
                attributes=attributes,
                tags=self._translator.from_linode(strings=tags),
            ))

            if inst.vpn_join is not None:
                result.vpn_records.append({
                    "instance_name": inst.name,
                    "instance_id": getattr(created, "id", ""),
                    "vpn_provider": inst.vpn_join.provider,
                    "vpn_device_id": vpn_device_id,
                })

        for vol in spec.volumes:
            existing = self._reader.find_volume(name=vol.name)
            if existing is not None:
                result.skipped.append(vol.name)
                continue
            tags = self._translator.owner_tags(
                run_id=run_id, resource_name=vol.name,
                resource_kind="volume", extra=list(vol.tags),
                defaults=defaults,
            )
            attach_handle = None
            if vol.attached_to is not None:
                attach_handle = instance_state.get(vol.attached_to, None)
            created = self._client.volume_create(
                label="automojo-{}-{}".format(run_id, vol.name),
                region=self._region_config.region, size=vol.size_gb,
                tags=tags, linode=attach_handle,
            )
            result.created.append(ProvisionedResource(
                kind="volume", name=vol.name,
                venue_id=str(getattr(created, "id", "")),
                attributes={"volume_id": getattr(created, "id", ""),
                            "size_gb": vol.size_gb},
                tags=self._translator.from_linode(strings=tags),
            ))

        rtnval = instance_state
        return rtnval

    def apply_object_storage_and_dns(self, *, spec: LinodeSpec, run_id: str,
                                     result: LinodeApplyResult,
                                     aspects: Any) -> None:
        """
            Apply Object Storage buckets and Linode DNS records.

            :param spec: The LinodeSpec.
            :param run_id: The run identifier.
            :param result: The LinodeApplyResult accumulator.
            :param aspects: Aspects.
        """
        for bucket in spec.buckets:
            existing = self._reader.find_bucket(name=bucket.name)
            if existing is not None:
                result.skipped.append(bucket.name)
                continue
            cluster = bucket.region
            if cluster is None or len(cluster) == 0:
                cluster = self._region_config.object_storage_cluster
            created = self._client.object_storage.bucket_create(
                cluster=cluster, label=bucket.name,
            )
            result.created.append(ProvisionedResource(
                kind="bucket", name=bucket.name,
                venue_id=str(getattr(created, "id", bucket.name)),
                attributes={"cluster": cluster}, tags=[],
            ))

        for record in spec.dns_records:
            existing = self._reader.find_dns_record(zone=record.zone,
                                                    name=record.name)
            if existing is not None:
                result.skipped.append(record.name)
                continue
            domain = self._reader.find_domain(zone=record.zone)
            if domain is None:
                domain = self._client.domain_create(
                    domain=record.zone, soa_email="admin@{}".format(
                        record.zone
                    ),
                )
            target_value = ""
            if record.values is not None and len(record.values) > 0:
                target_value = record.values[0]
            created = domain.record_create(
                record_type=record.record_type, name=record.name,
                target=target_value, ttl_sec=record.ttl_seconds,
            )
            result.created.append(ProvisionedResource(
                kind="dns", name=record.name,
                venue_id=str(getattr(created, "id", record.name)),
                attributes={"zone": record.zone,
                            "record_type": record.record_type},
                tags=[],
            ))
        return

    @staticmethod
    def _accelerator_models(*, instance: Any) -> List[str]:
        """
            Extract the neutral accelerator model strings from an instance.

            :param instance: A CloudInstance.

            :returns: A list of model strings (possibly empty).
        """
        accelerators = instance.accelerators if instance.accelerators is not None else []
        out: List[str] = []
        for entry in accelerators:
            out.append(entry.model)
        rtnval = out
        return rtnval

    @staticmethod
    def _firewall_rules(*, sg: Any) -> Dict[str, Any]:
        """
            Translate a CloudSecurityGroup into Linode firewall rules.

            :param sg: A CloudSecurityGroup.

            :returns: A Linode firewall ``rules`` dict.
        """
        inbound: List[Dict[str, Any]] = []
        ingress = sg.ingress_rules if sg.ingress_rules is not None else []
        for rule in ingress:
            ports = "{}".format(rule.from_port)
            if rule.to_port != rule.from_port:
                ports = "{}-{}".format(rule.from_port, rule.to_port)
            addresses = rule.source_cidrs if rule.source_cidrs is not None else []
            inbound.append({
                "action": "ACCEPT",
                "protocol": rule.protocol.upper(),
                "ports": ports,
                "addresses": {"ipv4": list(addresses)},
                "label": "ingress-{}".format(rule.from_port),
            })

        outbound: List[Dict[str, Any]] = []
        egress = sg.egress_rules if sg.egress_rules is not None else []
        for rule in egress:
            ports = "{}".format(rule.from_port)
            if rule.to_port != rule.from_port:
                ports = "{}-{}".format(rule.from_port, rule.to_port)
            addresses = rule.dest_cidrs if rule.dest_cidrs is not None else []
            outbound.append({
                "action": "ACCEPT",
                "protocol": rule.protocol.upper(),
                "ports": ports,
                "addresses": {"ipv4": list(addresses)},
                "label": "egress-{}".format(rule.from_port),
            })

        rtnval: Dict[str, Any] = {
            "inbound": inbound,
            "inbound_policy": "DROP",
            "outbound": outbound,
            "outbound_policy": "ACCEPT",
        }
        return rtnval
