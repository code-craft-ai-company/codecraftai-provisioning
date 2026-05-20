"""
    .. module:: vultrapplystages
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: VultrApplyStages — idempotent create-or-reuse apply stages.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import ipaddress

from typing import Any, Dict, List, Optional

from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.venues.vultr.vultrclient import VultrClient
from automojo.provisioning.venues.vultr.vultrresolver import VultrResolver
from automojo.provisioning.venues.vultr.vultrresources import (
    find_named, neutral_tags_of
)
from automojo.provisioning.venues.vultr.vultrtagtranslator import (
    VultrTagTranslator
)
from automojo.provisioning.venues.vultr.vultruserdatarenderer import (
    VultrUserDataRenderer
)


class VultrApplyStages:
    """
        Idempotent apply stages for the Vultr venue.

        Each stage performs an owner-tagged read-before-create so that
        ``apply ∘ apply`` is the identity.  Stages return
        :class:`ProvisionedResource` records plus a per-stage ``existed`` map
        so the provisioner can classify created vs. skipped resources.
    """

    def __init__(self, *, client: VultrClient, resolver: VultrResolver
                 ) -> None:
        """
            Construct a VultrApplyStages.

            :param client: A VultrClient.
            :param resolver: A VultrResolver.
        """
        self._client: VultrClient = client
        self._resolver: VultrResolver = resolver
        self._renderer: VultrUserDataRenderer = VultrUserDataRenderer()
        return

    # ------------------------------------------------------------------
    # Stage 1: VPC + Firewall + SSH keys
    # ------------------------------------------------------------------

    def apply_network_and_firewall(self, *, spec: Any, run_id: str,
                                   default_tags: List[Dict[str, str]]
                                   ) -> Dict[str, Any]:
        """
            Apply VPC 2.0, Firewall Groups + rules, and SSH keys.

            :param spec: The VultrSpec.
            :param run_id: The provisioning run identifier.
            :param default_tags: Venue default neutral tags.

            :returns: A dict with ``networks`` / ``firewalls`` / ``keypairs``
                      state plus a ``created`` / ``skipped`` classification.
        """
        created: List[ProvisionedResource] = []
        skipped: List[str] = []
        networks: Dict[str, ProvisionedResource] = {}
        firewalls: Dict[str, ProvisionedResource] = {}
        keypairs: Dict[str, ProvisionedResource] = {}

        for net in spec.networks:
            existing = find_named(client=self._client, path="/vpc2",
                                  collection_key="vpcs", run_id=run_id,
                                  name=net.name)
            if existing is None:
                tags = VultrTagTranslator.base_resource_tags(
                    run_id=run_id, resource_name=net.name,
                    resource_kind="network", extra=list(net.tags),
                    defaults=default_tags,
                )
                v4_subnet, v4_mask = self._split_cidr(cidr=net.cidr)
                body = {
                    "region": net.region,
                    "description": net.name,
                    "v4_subnet": v4_subnet,
                    "v4_subnet_mask": v4_mask,
                    "tags": tags,
                }
                response = self._client.post(path="/vpc2", json_body=body)
                existing = response.get("vpc", {})
                resource = self._network_resource(entry=existing, name=net.name)
                networks[net.name] = resource
                created.append(resource)
            else:
                resource = self._network_resource(entry=existing,
                                                  name=net.name)
                networks[net.name] = resource
                skipped.append(net.name)

        for sg in spec.security_groups:
            existing = find_named(client=self._client, path="/firewalls",
                                  collection_key="firewall_groups",
                                  run_id=run_id, name=sg.name)
            if existing is None:
                tags = VultrTagTranslator.base_resource_tags(
                    run_id=run_id, resource_name=sg.name,
                    resource_kind="sg", extra=list(sg.tags),
                    defaults=default_tags,
                )
                # Vultr firewall groups are described by a single string and
                # carry no native tag list; encode the owner tags into the
                # description so listings stay owner-filterable.
                description = "{} [{}]".format(sg.name, ",".join(tags))
                response = self._client.post(
                    path="/firewalls",
                    json_body={"description": description},
                )
                existing = response.get("firewall_group", {})
                group_id = existing.get("id", "")
                self._apply_firewall_rules(group_id=group_id, sg=sg)
                resource = self._firewall_resource(entry=existing, name=sg.name,
                                                   tags=tags)
                firewalls[sg.name] = resource
                created.append(resource)
            else:
                resource = self._firewall_resource(
                    entry=existing, name=sg.name,
                    tags=self._tags_from_description(
                        description=existing.get("description", "")
                    ),
                )
                firewalls[sg.name] = resource
                skipped.append(sg.name)

        for kp in spec.keypairs:
            existing = find_named(client=self._client, path="/ssh-keys",
                                  collection_key="ssh_keys", run_id=run_id,
                                  name=kp.name)
            if existing is None:
                tags = VultrTagTranslator.base_resource_tags(
                    run_id=run_id, resource_name=kp.name,
                    resource_kind="keypair", defaults=default_tags,
                )
                # SSH keys carry no native tags; the owner tags ride in the
                # name so subsequent listings remain owner-filterable.
                tagged_name = "{}|{}".format(kp.name, ",".join(tags))
                response = self._client.post(
                    path="/ssh-keys",
                    json_body={"name": tagged_name,
                               "ssh_key": kp.public_key_material},
                )
                existing = response.get("ssh_key", {})
                resource = self._keypair_resource(entry=existing, name=kp.name,
                                                  tags=tags)
                keypairs[kp.name] = resource
                created.append(resource)
            else:
                resource = self._keypair_resource(
                    entry=existing, name=kp.name,
                    tags=self._tags_from_name(
                        tagged_name=existing.get("name", "")
                    ),
                )
                keypairs[kp.name] = resource
                skipped.append(kp.name)

        rtnval = {
            "networks": networks,
            "firewalls": firewalls,
            "keypairs": keypairs,
            "created": created,
            "skipped": skipped,
        }
        return rtnval

    # ------------------------------------------------------------------
    # Stage 2: Instances + Block Storage
    # ------------------------------------------------------------------

    def apply_instances_and_blocks(self, *, spec: Any, run_id: str,
                                   default_tags: List[Dict[str, str]],
                                   networks: Dict[str, ProvisionedResource],
                                   firewalls: Dict[str, ProvisionedResource],
                                   keypairs: Dict[str, ProvisionedResource],
                                   authkey: str) -> Dict[str, Any]:
        """
            Apply Instances (with base64 user_data) and Block Storage.

            :param spec: The VultrSpec.
            :param run_id: The provisioning run identifier.
            :param default_tags: Venue default neutral tags.
            :param networks: Network state from stage 1.
            :param firewalls: Firewall state from stage 1.
            :param keypairs: SSH key state from stage 1.
            :param authkey: Minted VPN auth-key (when vpn_join present).

            :returns: A dict with ``instances`` state plus ``created`` /
                      ``skipped`` classification and ``vpn_records``.
        """
        created: List[ProvisionedResource] = []
        skipped: List[str] = []
        instances: Dict[str, ProvisionedResource] = {}
        vpn_records: List[Dict[str, Any]] = []

        for inst in spec.instances:
            existing = find_named(client=self._client, path="/instances",
                                  collection_key="instances", run_id=run_id,
                                  name=inst.name)
            if existing is None:
                tags = VultrTagTranslator.base_resource_tags(
                    run_id=run_id, resource_name=inst.name,
                    resource_kind="instance", extra=list(inst.tags),
                    defaults=default_tags,
                )
                os_id = self._resolver.image_to_os_id(
                    family=inst.image.family, version=inst.image.version,
                    arch=inst.image.architecture,
                )
                plan = self._resolver.size_to_plan(
                    size_hint=inst.size, accelerators=inst.accelerators,
                )
                user_data = self._renderer.render_base64(
                    instance=inst, authkey=authkey,
                )

                vpc_ids: List[str] = []
                if inst.subnet is not None and inst.subnet in networks:
                    vpc_ids.append(
                        networks[inst.subnet].attributes.get("vpc_id", "")
                    )
                for net_name in networks:
                    net_id = networks[net_name].attributes.get("vpc_id", "")
                    if net_id not in vpc_ids and len(vpc_ids) == 0:
                        vpc_ids.append(net_id)

                sshkey_ids: List[str] = []
                if inst.keypair is not None and inst.keypair in keypairs:
                    sshkey_ids.append(
                        keypairs[inst.keypair].venue_id
                    )

                firewall_id = ""
                ref_sgs = (inst.security_groups
                           if inst.security_groups is not None else [])
                for sg_name in ref_sgs:
                    if sg_name in firewalls:
                        firewall_id = firewalls[sg_name].venue_id

                body: Dict[str, Any] = {
                    "region": self._instance_region(instance=inst, spec=spec),
                    "plan": plan,
                    "os_id": os_id,
                    "label": inst.name,
                    "tags": tags,
                    "hostname": inst.name,
                    "backups": "disabled",
                }
                if len(user_data) > 0:
                    body["user_data"] = user_data
                if len(vpc_ids) > 0 and len(vpc_ids[0]) > 0:
                    body["attach_vpc2"] = [v for v in vpc_ids if len(v) > 0]
                if len(sshkey_ids) > 0:
                    body["sshkey_id"] = sshkey_ids
                if len(firewall_id) > 0:
                    body["firewall_group_id"] = firewall_id
                if inst.public_ip is True:
                    body["enable_ipv6"] = False

                response = self._client.post(path="/instances",
                                             json_body=body)
                existing = response.get("instance", {})
                resource = self._instance_resource(entry=existing,
                                                   name=inst.name, plan=plan,
                                                   os_id=os_id)
                instances[inst.name] = resource
                created.append(resource)
                if inst.vpn_join is not None:
                    vpn_records.append({
                        "instance_name": inst.name,
                        "instance_id": resource.venue_id,
                        "vpn_provider": inst.vpn_join.provider,
                        "vpn_device_id": None,
                    })
            else:
                resource = self._instance_resource(
                    entry=existing, name=inst.name,
                    plan=existing.get("plan", ""),
                    os_id=existing.get("os_id", 0),
                )
                instances[inst.name] = resource
                skipped.append(inst.name)

        for vol in spec.volumes:
            existing = find_named(client=self._client, path="/blocks",
                                  collection_key="blocks", run_id=run_id,
                                  name=vol.name)
            if existing is None:
                tags = VultrTagTranslator.base_resource_tags(
                    run_id=run_id, resource_name=vol.name,
                    resource_kind="volume", extra=list(vol.tags),
                    defaults=default_tags,
                )
                region = self._block_region(volume=vol, spec=spec)
                tagged_label = "{}|{}".format(vol.name, ",".join(tags))
                body = {
                    "region": region,
                    "size_gb": vol.size_gb,
                    "label": tagged_label,
                }
                response = self._client.post(path="/blocks", json_body=body)
                block = response.get("block", {})
                block_id = block.get("id", "")
                if vol.attached_to is not None and vol.attached_to in instances:
                    target_id = instances[vol.attached_to].venue_id
                    self._client.post(
                        path="/blocks/{}/attach".format(block_id),
                        json_body={"instance_id": target_id},
                    )
                resource = self._block_resource(entry=block, name=vol.name,
                                                tags=tags)
                created.append(resource)
            else:
                skipped.append(vol.name)

        rtnval = {
            "instances": instances,
            "created": created,
            "skipped": skipped,
            "vpn_records": vpn_records,
        }
        return rtnval

    # ------------------------------------------------------------------
    # Stage 3: Object Storage + DNS
    # ------------------------------------------------------------------

    def apply_object_storage_and_dns(self, *, spec: Any, run_id: str
                                     ) -> Dict[str, Any]:
        """
            Apply Object Storage subscriptions and DNS records.

            :param spec: The VultrSpec.
            :param run_id: The provisioning run identifier.

            :returns: A dict with ``created`` / ``skipped`` classification.
        """
        created: List[ProvisionedResource] = []
        skipped: List[str] = []

        for bucket in spec.buckets:
            existing = find_named(client=self._client,
                                  path="/object-storage",
                                  collection_key="object_storages",
                                  run_id=run_id, name=bucket.name)
            if existing is None:
                cluster_id = self._object_cluster_id(bucket=bucket)
                tags = VultrTagTranslator.base_resource_tags(
                    run_id=run_id, resource_name=bucket.name,
                    resource_kind="bucket", extra=list(bucket.tags),
                )
                tagged_label = "{}|{}".format(bucket.name, ",".join(tags))
                response = self._client.post(
                    path="/object-storage",
                    json_body={"cluster_id": cluster_id,
                               "label": tagged_label},
                )
                obj = response.get("object_storage", {})
                resource = ProvisionedResource(
                    kind="bucket", name=bucket.name,
                    venue_id=str(obj.get("id", "")),
                    attributes={"cluster_id": cluster_id,
                                "region": bucket.region},
                )
                created.append(resource)
            else:
                skipped.append(bucket.name)

        for record in spec.dns_records:
            for value in record.values:
                self._client.post(
                    path="/domains/{}/records".format(record.zone),
                    json_body={
                        "name": record.name,
                        "type": record.record_type,
                        "data": value,
                        "ttl": record.ttl_seconds,
                    },
                )
            resource = ProvisionedResource(
                kind="dns", name=record.name,
                venue_id="{}/{}".format(record.zone, record.name),
                attributes={"zone": record.zone,
                            "type": record.record_type},
            )
            created.append(resource)

        rtnval = {
            "created": created,
            "skipped": skipped,
        }
        return rtnval

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _apply_firewall_rules(self, *, group_id: str, sg: Any) -> None:
        """
            Create the firewall rules for an SG's ingress declarations.

            :param group_id: The Vultr firewall group id.
            :param sg: The CloudSecurityGroup.
        """
        rules = sg.ingress_rules if sg.ingress_rules is not None else []
        for rule in rules:
            cidrs = (rule.source_cidrs
                     if rule.source_cidrs is not None else ["0.0.0.0/0"])
            for cidr in cidrs:
                network = ipaddress.ip_network(cidr, strict=False)
                subnet_size = network.prefixlen
                subnet_addr = str(network.network_address)
                body = {
                    "ip_type": "v4",
                    "protocol": rule.protocol,
                    "subnet": subnet_addr,
                    "subnet_size": subnet_size,
                    "port": "{}:{}".format(rule.from_port, rule.to_port),
                }
                self._client.post(
                    path="/firewalls/{}/rules".format(group_id),
                    json_body=body,
                )
        return

    @staticmethod
    def _split_cidr(*, cidr: str) -> Any:
        """
            Split a CIDR string into address + mask.

            :param cidr: A CIDR string.

            :returns: A tuple of (address, prefixlen).
        """
        network = ipaddress.ip_network(cidr, strict=False)
        rtnval = (str(network.network_address), network.prefixlen)
        return rtnval

    @staticmethod
    def _tags_from_description(*, description: str) -> List[str]:
        """
            Recover owner tag strings encoded in a firewall description.

            :param description: The firewall group description.

            :returns: A list of tag strings.
        """
        out: List[str] = []
        start = description.find("[")
        end = description.find("]")
        if start >= 0 and end > start:
            inner = description[start + 1:end]
            for piece in inner.split(","):
                if len(piece) > 0:
                    out.append(piece)
        rtnval = out
        return rtnval

    @staticmethod
    def _tags_from_name(*, tagged_name: str) -> List[str]:
        """
            Recover owner tag strings encoded in an SSH key name.

            :param tagged_name: The tagged SSH key name.

            :returns: A list of tag strings.
        """
        out: List[str] = []
        if "|" in tagged_name:
            inner = tagged_name.split("|", 1)[1]
            for piece in inner.split(","):
                if len(piece) > 0:
                    out.append(piece)
        rtnval = out
        return rtnval

    @staticmethod
    def _instance_region(*, instance: Any, spec: Any) -> str:
        """
            Resolve the region for an instance from its subnet's network.

            :param instance: The CloudInstance.
            :param spec: The VultrSpec.

            :returns: A region slug.
        """
        for net in spec.networks:
            if net.name == instance.subnet:
                rtnval = net.region
                return rtnval
        if len(spec.networks) > 0:
            rtnval = spec.networks[0].region
            return rtnval
        rtnval = "ewr"
        return rtnval

    @staticmethod
    def _block_region(*, volume: Any, spec: Any) -> str:
        """
            Resolve the region for a block volume from the spec networks.

            :param volume: The CloudStorageVolume.
            :param spec: The VultrSpec.

            :returns: A region slug.
        """
        if len(spec.networks) > 0:
            rtnval = spec.networks[0].region
            return rtnval
        rtnval = "ewr"
        return rtnval

    @staticmethod
    def _object_cluster_id(*, bucket: Any) -> int:
        """
            Resolve the Vultr object-storage cluster id for a bucket region.

            :param bucket: The CloudObjectBucket.

            :returns: An integer cluster id.
        """
        rtnval = 2
        return rtnval

    @staticmethod
    def _network_resource(*, entry: Dict[str, Any], name: str
                          ) -> ProvisionedResource:
        """
            Build a ProvisionedResource for a VPC entry.

            :param entry: The Vultr ``vpc`` API dict.
            :param name: The neutral network name.

            :returns: A ProvisionedResource.
        """
        vpc_id = str(entry.get("id", ""))
        attributes = {
            "vpc_id": vpc_id,
            "region": entry.get("region", ""),
            "v4_subnet": entry.get("v4_subnet", ""),
            "v4_subnet_mask": entry.get("v4_subnet_mask", 0),
        }
        rtnval = ProvisionedResource(
            kind="network", name=name, venue_id=vpc_id,
            attributes=attributes, tags=neutral_tags_of(entry=entry),
        )
        return rtnval

    @staticmethod
    def _firewall_resource(*, entry: Dict[str, Any], name: str,
                           tags: List[str]) -> ProvisionedResource:
        """
            Build a ProvisionedResource for a firewall group entry.

            :param entry: The Vultr ``firewall_group`` API dict.
            :param name: The neutral SG name.
            :param tags: The owner tag strings.

            :returns: A ProvisionedResource.
        """
        group_id = str(entry.get("id", ""))
        rtnval = ProvisionedResource(
            kind="sg", name=name, venue_id=group_id,
            attributes={"firewall_group_id": group_id},
            tags=VultrTagTranslator.from_vultr(strings=tags),
        )
        return rtnval

    @staticmethod
    def _keypair_resource(*, entry: Dict[str, Any], name: str,
                          tags: List[str]) -> ProvisionedResource:
        """
            Build a ProvisionedResource for an SSH key entry.

            :param entry: The Vultr ``ssh_key`` API dict.
            :param name: The neutral keypair name.
            :param tags: The owner tag strings.

            :returns: A ProvisionedResource.
        """
        key_id = str(entry.get("id", ""))
        rtnval = ProvisionedResource(
            kind="keypair", name=name, venue_id=key_id,
            attributes={"sshkey_id": key_id},
            tags=VultrTagTranslator.from_vultr(strings=tags),
        )
        return rtnval

    @staticmethod
    def _instance_resource(*, entry: Dict[str, Any], name: str, plan: Any,
                           os_id: Any) -> ProvisionedResource:
        """
            Build a ProvisionedResource for an instance entry.

            :param entry: The Vultr ``instance`` API dict.
            :param name: The neutral instance name.
            :param plan: The resolved Vultr plan id.
            :param os_id: The resolved Vultr os id.

            :returns: A ProvisionedResource.
        """
        instance_id = str(entry.get("id", ""))
        attributes = {
            "instance_id": instance_id,
            "plan": plan,
            "os_id": os_id,
            "main_ip": entry.get("main_ip", ""),
        }
        rtnval = ProvisionedResource(
            kind="instance", name=name, venue_id=instance_id,
            attributes=attributes, tags=neutral_tags_of(entry=entry),
        )
        return rtnval

    @staticmethod
    def _block_resource(*, entry: Dict[str, Any], name: str,
                        tags: List[str]) -> ProvisionedResource:
        """
            Build a ProvisionedResource for a block-storage entry.

            :param entry: The Vultr ``block`` API dict.
            :param name: The neutral volume name.
            :param tags: The owner tag strings.

            :returns: A ProvisionedResource.
        """
        block_id = str(entry.get("id", ""))
        rtnval = ProvisionedResource(
            kind="volume", name=name, venue_id=block_id,
            attributes={"block_id": block_id,
                        "size_gb": entry.get("size_gb", 0)},
            tags=VultrTagTranslator.from_vultr(strings=tags),
        )
        return rtnval
