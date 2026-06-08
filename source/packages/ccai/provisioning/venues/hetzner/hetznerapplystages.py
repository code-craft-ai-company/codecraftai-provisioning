"""
    .. module:: hetznerapplystages
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: HetznerApplyStages — idempotent match-then-act apply stages.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Optional

from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.venues.hetzner.hetznererrors import (
    HetznerValidationError
)
from ccai.provisioning.venues.hetzner.hetznerlabeltranslator import (
    HetznerLabelTranslator
)
from ccai.provisioning.venues.hetzner.hetznerresolver import (
    HetznerResolver
)
from ccai.provisioning.venues.hetzner.hetznerspec import HetznerSpec
from ccai.provisioning.venues.hetzner.hetzneruserdatarenderer import (
    HetznerUserDataRenderer
)


def _labels_of(obj: Any) -> Dict[str, str]:
    """
        Read the ``labels`` dict off an hcloud-shaped object.

        :param obj: An hcloud resource object.

        :returns: The labels dict (empty when absent).
    """
    labels = getattr(obj, "labels", None)
    if labels is None:
        rtnval: Dict[str, str] = {}
        return rtnval
    rtnval = dict(labels)
    return rtnval


def _id_of(obj: Any) -> str:
    """
        Read the ``id`` attribute off an hcloud-shaped object as a string.

        :param obj: An hcloud resource object.

        :returns: The string id (empty when absent).
    """
    raw_id = getattr(obj, "id", None)
    if raw_id is None:
        rtnval = ""
        return rtnval
    rtnval = str(raw_id)
    return rtnval


class HetznerApplyStages:
    """
        Stage helpers realising the Hetzner apply lifecycle.

        Apply order is Network -> Firewall -> SSH Key -> Server -> Volume ->
        DNS.  Every stage reads-before-create by name and reuses an existing
        owned resource when its mutable attributes match.
    """

    def __init__(self, *, client: Any,
                 default_labels: Dict[str, str],
                 dns_client: Optional[Any] = None) -> None:
        """
            Construct a HetznerApplyStages.

            :param client: An hcloud Client (or mock).
            :param default_labels: Venue default labels.
            :param dns_client: Optional Hetzner DNS API client (or mock).
        """
        self._client: Any = client
        self._default_labels: Dict[str, str] = dict(default_labels)
        self._dns_client: Optional[Any] = dns_client
        return

    def apply_network_and_firewall(self, *, spec: HetznerSpec,
                                   run_id: str, aspects: Any,
                                   created: List[ProvisionedResource],
                                   skipped: List[str]
                                   ) -> Dict[str, ProvisionedResource]:
        """
            Ensure Networks then Firewalls for the spec.

            :param spec: The HetznerSpec.
            :param run_id: Run identifier.
            :param aspects: ProvisioningAspects.
            :param created: List to append newly created resources to.
            :param skipped: List to append skipped resource names to.

            :returns: A dict of network-name -> ProvisionedResource.
        """
        network_state: Dict[str, ProvisionedResource] = {}

        for net in spec.networks:
            existing = self._client.networks.get_by_name(name=net.name)
            owned = existing is not None and (
                HetznerLabelTranslator.belongs_to_run(
                    labels=_labels_of(existing), run_id=run_id))
            if owned is True:
                resource = self._resource_from_network(net=net,
                                                       live=existing)
                network_state[net.name] = resource
                skipped.append(net.name)
                continue

            labels = HetznerLabelTranslator.base_labels(
                run_id=run_id, resource_name=net.name,
                resource_kind="network", extra=dict(net.tags),
                defaults=self._default_labels)
            live = self._client.networks.create(
                name=net.name, ip_range=net.cidr, labels=labels)
            resource = self._resource_from_network(net=net, live=live)
            network_state[net.name] = resource
            created.append(resource)

        for sg in spec.security_groups:
            existing = self._client.firewalls.get_by_name(name=sg.name)
            owned = existing is not None and (
                HetznerLabelTranslator.belongs_to_run(
                    labels=_labels_of(existing), run_id=run_id))
            if owned is True:
                skipped.append(sg.name)
                continue

            labels = HetznerLabelTranslator.base_labels(
                run_id=run_id, resource_name=sg.name,
                resource_kind="security_group", extra=dict(sg.tags),
                defaults=self._default_labels)
            rules = self._firewall_rules_for(sg=sg)
            live = self._client.firewalls.create(
                name=sg.name, rules=rules, labels=labels)
            resource = ProvisionedResource(
                kind="security_group", name=sg.name,
                venue_id=_id_of(live),
                attributes={"firewall_id": _id_of(live)},
                tags=HetznerLabelTranslator.from_hetzner(
                    labels=_labels_of(live)))
            created.append(resource)

        rtnval = network_state
        return rtnval

    def apply_servers_and_volumes(self, *, spec: HetznerSpec,
                                  run_id: str, aspects: Any,
                                  authkey_for: Dict[str, str],
                                  created: List[ProvisionedResource],
                                  updated: List[ProvisionedResource],
                                  skipped: List[str],
                                  vpn_records: List[Dict[str, Any]]
                                  ) -> Dict[str, ProvisionedResource]:
        """
            Ensure SSH keys, then Servers, then Volumes.

            :param spec: The HetznerSpec.
            :param run_id: Run identifier.
            :param aspects: ProvisioningAspects.
            :param authkey_for: Map of instance-name -> minted VPN authkey.
            :param created: List to append newly created resources to.
            :param updated: List to append in-place updated resources to.
            :param skipped: List to append skipped resource names to.
            :param vpn_records: List to append vpn-device records to.

            :returns: A dict of instance-name -> ProvisionedResource.
        """
        ssh_key_state: Dict[str, Any] = {}
        for kp in spec.keypairs:
            existing = self._client.ssh_keys.get_by_name(name=kp.name)
            if existing is not None:
                ssh_key_state[kp.name] = existing
                skipped.append(kp.name)
                continue
            labels = HetznerLabelTranslator.base_labels(
                run_id=run_id, resource_name=kp.name,
                resource_kind="keypair",
                defaults=self._default_labels)
            live = self._client.ssh_keys.create(
                name=kp.name, public_key=kp.public_key_material,
                labels=labels)
            ssh_key_state[kp.name] = live
            created.append(ProvisionedResource(
                kind="keypair", name=kp.name, venue_id=_id_of(live),
                attributes={"ssh_key_id": _id_of(live)},
                tags=HetznerLabelTranslator.from_hetzner(
                    labels=_labels_of(live))))

        instance_state: Dict[str, ProvisionedResource] = {}
        for inst in spec.instances:
            existing = self._client.servers.get_by_name(name=inst.name)
            owned = existing is not None and (
                HetznerLabelTranslator.belongs_to_run(
                    labels=_labels_of(existing), run_id=run_id))
            if owned is True:
                resource = ProvisionedResource(
                    kind="instance", name=inst.name,
                    venue_id=_id_of(existing),
                    attributes={"server_id": _id_of(existing)},
                    tags=HetznerLabelTranslator.from_hetzner(
                        labels=_labels_of(existing)))
                instance_state[inst.name] = resource
                skipped.append(inst.name)
                continue

            accel_models: List[str] = []
            if inst.accelerators is not None:
                for entry in inst.accelerators:
                    accel_models.append(entry.model)
            server_type = HetznerResolver.size_to_type(
                size_hint=inst.size, accelerators=accel_models)
            image_name = HetznerResolver.image_to_name(
                family=inst.image.family, version=inst.image.version,
                arch=inst.image.architecture)

            user_data: Optional[str] = None
            if inst.vpn_join is not None:
                authkey = authkey_for.get(inst.name, "")
                user_data = HetznerUserDataRenderer.render(
                    instance=inst, authkey=authkey,
                    rendered_hostname=inst.name)
            elif inst.user_data_script is not None:
                user_data = HetznerUserDataRenderer.render(instance=inst)

            ssh_keys: List[Any] = []
            if inst.keypair is not None:
                key_obj = ssh_key_state.get(inst.keypair, None)
                if key_obj is not None:
                    ssh_keys.append(key_obj)

            labels = HetznerLabelTranslator.base_labels(
                run_id=run_id, resource_name=inst.name,
                resource_kind="instance", extra=dict(inst.tags),
                defaults=self._default_labels)

            live = self._client.servers.create(
                name=inst.name, server_type=server_type,
                image=image_name, ssh_keys=ssh_keys,
                user_data=user_data, labels=labels)
            live_server = self._unwrap_server(result=live)

            resource = ProvisionedResource(
                kind="instance", name=inst.name,
                venue_id=_id_of(live_server),
                attributes={"server_id": _id_of(live_server),
                            "server_type": server_type,
                            "image": image_name},
                tags=HetznerLabelTranslator.from_hetzner(
                    labels=_labels_of(live_server)))
            instance_state[inst.name] = resource
            created.append(resource)

            if inst.vpn_join is not None:
                vpn_records.append({
                    "instance_name": inst.name,
                    "server_id": _id_of(live_server),
                    "vpn_provider": inst.vpn_join.provider,
                    "vpn_device_id": None,
                })

        for vol in spec.volumes:
            existing = self._client.volumes.get_by_name(name=vol.name)
            owned = existing is not None and (
                HetznerLabelTranslator.belongs_to_run(
                    labels=_labels_of(existing), run_id=run_id))
            if owned is True:
                reconciled = self._reconcile_volume(
                    vol=vol, existing=existing)
                if reconciled is not None:
                    updated.append(reconciled)
                else:
                    skipped.append(vol.name)
                continue

            labels = HetznerLabelTranslator.base_labels(
                run_id=run_id, resource_name=vol.name,
                resource_kind="volume", extra=dict(vol.tags),
                defaults=self._default_labels)
            live = self._client.volumes.create(
                name=vol.name, size=vol.size_gb, labels=labels)
            live_volume = self._unwrap_volume(result=live)

            attached_server_id: Optional[str] = None
            if vol.attached_to is not None:
                target = instance_state.get(vol.attached_to, None)
                if target is not None:
                    attached_server_id = target.attributes.get(
                        "server_id", "")
                    self._client.volumes.attach(
                        volume=live_volume,
                        server_id=attached_server_id)

            attrs: Dict[str, Any] = {"volume_id": _id_of(live_volume),
                                     "size_gb": vol.size_gb}
            if attached_server_id is not None:
                attrs["attached_server_id"] = attached_server_id
            created.append(ProvisionedResource(
                kind="volume", name=vol.name,
                venue_id=_id_of(live_volume), attributes=attrs,
                tags=HetznerLabelTranslator.from_hetzner(
                    labels=_labels_of(live_volume))))

        rtnval = instance_state
        return rtnval

    def apply_dns(self, *, spec: HetznerSpec, run_id: str, aspects: Any,
                  created: List[ProvisionedResource]) -> None:
        """
            Ensure Hetzner DNS records for the spec.

            :param spec: The HetznerSpec.
            :param run_id: Run identifier.
            :param aspects: ProvisioningAspects.
            :param created: List to append newly created resources to.
        """
        if self._dns_client is None:
            for record in spec.dns_records:
                created.append(ProvisionedResource(
                    kind="dns", name=record.name,
                    venue_id="dns-{}-{}".format(record.zone, record.name),
                    attributes={"zone": record.zone,
                                "record_type": record.record_type,
                                "note": "No DNS client configured; record "
                                        "registered logically only."}))
            return

        for record in spec.dns_records:
            zone_id = self._dns_client.get_zone_id(zone_name=record.zone)
            for value in record.values:
                live = self._dns_client.create_record(
                    zone_id=zone_id, name=record.name,
                    record_type=record.record_type, value=value,
                    ttl=record.ttl_seconds)
                created.append(ProvisionedResource(
                    kind="dns", name=record.name,
                    venue_id=_id_of(live),
                    attributes={"zone": record.zone, "zone_id": zone_id,
                                "record_type": record.record_type,
                                "value": value}))
        return

    def _reconcile_volume(self, *, vol: Any,
                          existing: Any) -> Optional[ProvisionedResource]:
        """
            Reconcile a live owned Volume against the spec, realising a
            size *grow* in place via the hcloud ``volume.resize`` call.

            Hetzner volumes support an online in-place grow; the resize is
            non-disruptive and is therefore not gated behind
            ``aspects.confirm``.  Hetzner volumes cannot shrink — a smaller
            desired size is an impossible request and is refused with a
            typed :class:`HetznerValidationError` rather than silently
            recreated.

            :param vol: The desired CloudStorageVolume.
            :param existing: The live hcloud volume object.

            :returns: A ProvisionedResource when the volume was grown in
                place; ``None`` when the volume was already in size-shape.

            :raises: HetznerValidationError when a shrink is requested.
        """
        live_size = getattr(existing, "size", None)
        if live_size is None or live_size == vol.size_gb:
            rtnval: Optional[ProvisionedResource] = None
            return rtnval

        if vol.size_gb < live_size:
            err_msg_lines = [
                "Hetzner volume cannot be shrunk; hcloud volumes only "
                "support an in-place grow."
            ]
            err_msg_lines.append("VOLUME: {}".format(vol.name))
            err_msg_lines.append("    live size_gb:    {}".format(
                live_size))
            err_msg_lines.append("    desired size_gb: {}".format(
                vol.size_gb))
            err_msg = os.linesep.join(err_msg_lines)
            raise HetznerValidationError(err_msg)

        self._client.volumes.resize(volume=existing, size=vol.size_gb)
        setattr(existing, "size", vol.size_gb)

        attrs: Dict[str, Any] = {"volume_id": _id_of(existing),
                                 "size_gb": vol.size_gb}
        attached_server_id = getattr(existing, "attached_server_id", None)
        if attached_server_id is not None:
            attrs["attached_server_id"] = attached_server_id
        rtnval = ProvisionedResource(
            kind="volume", name=vol.name, venue_id=_id_of(existing),
            attributes=attrs,
            tags=HetznerLabelTranslator.from_hetzner(
                labels=_labels_of(existing)))
        return rtnval

    @classmethod
    def _resource_from_network(cls, *, net: Any,
                               live: Any) -> ProvisionedResource:
        """
            Build a ProvisionedResource for a Hetzner Network.

            :param net: The desired CloudNetwork.
            :param live: The live hcloud network object.

            :returns: A ProvisionedResource.
        """
        rtnval = ProvisionedResource(
            kind="network", name=net.name, venue_id=_id_of(live),
            attributes={"network_id": _id_of(live),
                        "ip_range": getattr(live, "ip_range", net.cidr)},
            tags=HetznerLabelTranslator.from_hetzner(
                labels=_labels_of(live)))
        return rtnval

    @classmethod
    def _firewall_rules_for(cls, *, sg: Any) -> List[Dict[str, Any]]:
        """
            Translate neutral security-group rules into Hetzner firewall
            rule dicts.

            :param sg: The CloudSecurityGroup.

            :returns: A list of Hetzner firewall rule dicts.
        """
        rules: List[Dict[str, Any]] = []
        ingress = sg.ingress_rules if sg.ingress_rules is not None else []
        for rule in ingress:
            port_value = "{}-{}".format(rule.from_port, rule.to_port)
            if rule.from_port == rule.to_port:
                port_value = str(rule.from_port)
            source_cidrs = list(rule.source_cidrs)
            rules.append({"direction": "in", "protocol": rule.protocol,
                          "port": port_value, "source_ips": source_cidrs})
        rtnval = rules
        return rtnval

    @classmethod
    def _unwrap_server(cls, *, result: Any) -> Any:
        """
            Unwrap a server object from an hcloud create-server response.

            The hcloud SDK returns a ``CreateServerResponse`` carrying a
            ``.server`` attribute; tests may return the server directly.

            :param result: The create response or server object.

            :returns: The server object.
        """
        server = getattr(result, "server", None)
        if server is not None:
            rtnval = server
            return rtnval
        rtnval = result
        return rtnval

    @classmethod
    def _unwrap_volume(cls, *, result: Any) -> Any:
        """
            Unwrap a volume object from an hcloud create-volume response.

            :param result: The create response or volume object.

            :returns: The volume object.
        """
        volume = getattr(result, "volume", None)
        if volume is not None:
            rtnval = volume
            return rtnval
        rtnval = result
        return rtnval
