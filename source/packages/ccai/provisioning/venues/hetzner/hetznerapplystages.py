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

from typing import Any, Dict, List, Optional, Set, Tuple

from ccai.errors.exceptions import ConfigurationError
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.venues.hetzner.hetznererrors import (
    ConfirmationRequiredError, HetznerValidationError
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

            :returns: A dict with ``"networks"`` and ``"firewalls"`` maps of
                neutral-name -> live hcloud handle, for the server stage to
                attach servers to their declared network and firewalls.
        """
        network_state: Dict[str, ProvisionedResource] = {}
        # Live hcloud handles threaded to the server stage so servers can be
        # attached to their declared network / firewalls at create time.
        network_handles: Dict[str, Any] = {}
        firewall_handles: Dict[str, Any] = {}

        for net in spec.networks:
            existing = self._client.networks.get_by_name(name=net.name)
            owned = existing is not None and (
                HetznerLabelTranslator.belongs_to_run(
                    labels=_labels_of(existing), run_id=run_id))
            if owned is True:
                resource = self._resource_from_network(net=net,
                                                       live=existing)
                network_state[net.name] = resource
                network_handles[net.name] = existing
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
            network_handles[net.name] = live
            created.append(resource)

        for sg in spec.security_groups:
            existing = self._client.firewalls.get_by_name(name=sg.name)
            owned = existing is not None and (
                HetznerLabelTranslator.belongs_to_run(
                    labels=_labels_of(existing), run_id=run_id))
            if owned is True:
                firewall_handles[sg.name] = existing
                skipped.append(sg.name)
                continue

            labels = HetznerLabelTranslator.base_labels(
                run_id=run_id, resource_name=sg.name,
                resource_kind="security_group", extra=dict(sg.tags),
                defaults=self._default_labels)
            rules = self._firewall_rules_for(sg=sg)
            live = self._client.firewalls.create(
                name=sg.name, rules=rules, labels=labels)
            firewall_handles[sg.name] = live
            resource = ProvisionedResource(
                kind="security_group", name=sg.name,
                venue_id=_id_of(live),
                attributes={"firewall_id": _id_of(live)},
                tags=HetznerLabelTranslator.from_hetzner(
                    labels=_labels_of(live)))
            created.append(resource)

        rtnval = {"networks": network_handles, "firewalls": firewall_handles}
        return rtnval

    def apply_servers_and_volumes(self, *, spec: HetznerSpec,
                                  run_id: str, aspects: Any,
                                  authkey_for: Dict[str, str],
                                  created: List[ProvisionedResource],
                                  updated: List[ProvisionedResource],
                                  skipped: List[str],
                                  vpn_records: List[Dict[str, Any]],
                                  network_handles: Optional[Dict[str, Any]] = None,
                                  firewall_handles: Optional[Dict[str, Any]] = None,
                                  location: Optional[str] = None
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
            :param network_handles: Map of network-name -> live hcloud Network,
                from apply_network_and_firewall.
            :param firewall_handles: Map of sg-name -> live hcloud Firewall,
                from apply_network_and_firewall.
            :param location: The Hetzner location (datacenter region) to place
                servers in.

            :returns: A dict of instance-name -> ProvisionedResource.
        """
        if network_handles is None:
            network_handles = {}
        if firewall_handles is None:
            firewall_handles = {}
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
            accel_models: List[str] = []
            if inst.accelerators is not None:
                for entry in inst.accelerators:
                    accel_models.append(entry.model)
            server_type = HetznerResolver.size_to_type(
                size_hint=inst.size, accelerators=accel_models)

            existing = self._client.servers.get_by_name(name=inst.name)
            owned = existing is not None and (
                HetznerLabelTranslator.belongs_to_run(
                    labels=_labels_of(existing), run_id=run_id))
            recreated = False
            if owned is True:
                live_type = getattr(
                    getattr(existing, "server_type", None), "name", None)
                if live_type == server_type:
                    resource = ProvisionedResource(
                        kind="instance", name=inst.name,
                        venue_id=_id_of(existing),
                        attributes={"server_id": _id_of(existing)},
                        tags=HetznerLabelTranslator.from_hetzner(
                            labels=_labels_of(existing)))
                    instance_state[inst.name] = resource
                    skipped.append(inst.name)
                    continue

                # Server-type drift is realised UPDATE-by-recreate (Hetzner has
                # no in-place server-type change).  A destroy+relaunch is
                # disruptive, so it is gated behind aspects.confirm; without it
                # the plan's UPDATE intent is refused rather than silently
                # skipped (the prior behaviour never converged).
                confirm = getattr(aspects, "confirm", False)
                if confirm is not True:
                    err_msg_lines = [
                        "Hetzner apply requires aspects.confirm=True to "
                        "realise a server-type change by recreate."]
                    err_msg_lines.append("INSTANCE: {}".format(inst.name))
                    err_msg_lines.append("    before: {}".format(live_type))
                    err_msg_lines.append("    after:  {}".format(server_type))
                    err_msg = os.linesep.join(err_msg_lines)
                    raise ConfirmationRequiredError(err_msg)

                self._client.servers.delete(server=existing)
                recreated = True

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

            # Attach the server to its declared private network (resolved
            # inst.subnet -> subnet.network), its declared firewalls, and the
            # configured location — previously omitted, so servers landed in
            # the default location, on no private network, protected by no
            # firewall.
            server_networks = self._networks_for_instance(
                spec=spec, instance=inst, network_handles=network_handles)
            server_firewalls = self._firewalls_for_instance(
                instance=inst, firewall_handles=firewall_handles)
            server_location = self._location_object(location=location)

            live = self._client.servers.create(
                name=inst.name, server_type=server_type,
                image=image_name, ssh_keys=ssh_keys,
                user_data=user_data, labels=labels,
                networks=server_networks if len(server_networks) > 0 else None,
                firewalls=(server_firewalls
                           if len(server_firewalls) > 0 else None),
                location=server_location)
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
            if recreated is True:
                updated.append(resource)
            else:
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
            # A spec that declares DNS records cannot be satisfied without a
            # DNS client.  Previously these were appended to `created` as
            # "registered logically only" — reporting resources that were
            # never provisioned.  Fail loudly instead of lying about success.
            if len(spec.dns_records) > 0:
                record_names = [record.name for record in spec.dns_records]
                err_msg_lines = [
                    "Hetzner spec declares DNS records but no DNS client is "
                    "configured; the records cannot be provisioned."
                ]
                err_msg_lines.append("RECORDS: {}".format(
                    ", ".join(record_names)))
                err_msg = os.linesep.join(err_msg_lines)
                raise ConfigurationError(err_msg)
            return

        # Idempotent upsert.  The DNS client exposes delete-by-(zone, name) but
        # no per-record read, so each (zone, name) is cleared once per apply
        # and its desired values re-created — a re-apply is the identity rather
        # than accumulating duplicate records.  Clearing once (not per record)
        # preserves multiple record types that share a name within one apply.
        cleared_names: Set[Tuple[str, str]] = set()
        for record in spec.dns_records:
            zone_id = self._dns_client.get_zone_id(zone_name=record.zone)
            clear_key = (record.zone, record.name)
            if clear_key not in cleared_names:
                self._dns_client.delete_records(zone_name=record.zone,
                                                name=record.name)
                cleared_names.add(clear_key)
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

    @staticmethod
    def _networks_for_instance(*, spec: HetznerSpec, instance: Any,
                               network_handles: Dict[str, Any]) -> List[Any]:
        """
            Resolve the live hcloud networks a server should attach to.

            The instance's declared subnet names a CloudSubnet whose parent
            network is the private network the server joins (the same
            subnet -> network resolution the AWS and GCP venues use).

            :param spec: The HetznerSpec.
            :param instance: The neutral CloudInstance.
            :param network_handles: Map of network-name -> live hcloud Network.

            :returns: A list of live hcloud Network handles (possibly empty).
        """
        subnet_name = getattr(instance, "subnet", None)
        if subnet_name is None:
            rtnval: List[Any] = []
            return rtnval

        network_name = None
        for subnet in spec.subnets:
            if subnet.name == subnet_name:
                network_name = subnet.network
                break

        if network_name is None:
            rtnval = []
            return rtnval

        handle = network_handles.get(network_name, None)
        if handle is None:
            rtnval = []
            return rtnval

        rtnval = [handle]
        return rtnval

    @staticmethod
    def _firewalls_for_instance(*, instance: Any,
                                firewall_handles: Dict[str, Any]) -> List[Any]:
        """
            Resolve the live hcloud firewalls a server should be protected by.

            :param instance: The neutral CloudInstance.
            :param firewall_handles: Map of sg-name -> live hcloud Firewall.

            :returns: A list of live hcloud Firewall handles (possibly empty).
        """
        out: List[Any] = []
        sg_names = (instance.security_groups
                    if instance.security_groups is not None else [])
        for sg_name in sg_names:
            handle = firewall_handles.get(sg_name, None)
            if handle is not None:
                out.append(handle)
        rtnval = out
        return rtnval

    @staticmethod
    def _location_object(*, location: Optional[str]) -> Optional[Any]:
        """
            Build an hcloud Location object from a location name.

            :param location: The Hetzner location name, or None.

            :returns: An hcloud ``Location``, or None when unspecified.
        """
        if location is None or len(location) == 0:
            rtnval: Optional[Any] = None
            return rtnval

        from hcloud.locations.domain import Location
        rtnval = Location(name=location)
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
