"""
    .. module:: metalapplystages
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: MetalApplyStages — owner-tagged read-before-create stages for
               the Equinix Metal venue apply lifecycle.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os
import time

from typing import Any, Dict, List, Optional

from automojo.provisioning.model.cloud.cloudinstance import CloudInstance
from automojo.provisioning.model.cloud.cloudkeypair import CloudKeyPair
from automojo.provisioning.model.cloud.cloudnetwork import CloudNetwork
from automojo.provisioning.model.cloud.cloudsubnet import CloudSubnet
from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.venues.equinix_metal.metalclient import MetalClient
from automojo.provisioning.venues.equinix_metal.metalerrors import (
    MetalCapacityError
)
from automojo.provisioning.venues.equinix_metal.metalresolver import (
    MetalResolver
)
from automojo.provisioning.venues.equinix_metal.metaltagtranslator import (
    MetalTagTranslator, base_resource_tags, OWNER_TAG_KEY, OWNER_TAG_VALUE,
    RUN_ID_TAG_KEY, RESOURCE_NAME_TAG_KEY, RESOURCE_KIND_TAG_KEY,
    VPN_PROVIDER_TAG_KEY, VPN_DEVICE_ID_TAG_KEY
)
from automojo.provisioning.venues.equinix_metal.metaluserdatarenderer import (
    MetalUserDataRenderer
)


# Device states Equinix Metal reports while a bare-metal server provisions.
_ACTIVE_DEVICE_STATES = frozenset({"active"})
_TERMINAL_FAILURE_STATES = frozenset({"failed"})


def _aspect_attr(*, aspects: Any, name: str, default: Any) -> Any:
    """
        Read a named attribute from an aspects object or dict.

        :param aspects: Aspects object or dict.
        :param name: Attribute name.
        :param default: Default if missing.

        :returns: The attribute value or default.
    """
    if aspects is None:
        rtnval = default
        return rtnval
    if isinstance(aspects, dict):
        rtnval = aspects.get(name, default)
        return rtnval
    rtnval = getattr(aspects, name, default)
    return rtnval


def _owned_by(*, tag_strings: Optional[List[str]], run_id: str,
              resource_name: Optional[str] = None,
              resource_kind: Optional[str] = None) -> bool:
    """
        Test whether a tag string list identifies an automojo-owned resource.

        :param tag_strings: Metal tag string list.
        :param run_id: The provisioning run identifier.
        :param resource_name: Optional resource name to also match.
        :param resource_kind: Optional resource kind to also match.

        :returns: True when the tags identify the owned resource.
    """
    flat = MetalTagTranslator.flat_dict(strings=tag_strings)
    if flat.get(OWNER_TAG_KEY, "") != OWNER_TAG_VALUE:
        rtnval = False
        return rtnval
    if flat.get(RUN_ID_TAG_KEY, "") != run_id:
        rtnval = False
        return rtnval
    if resource_name is not None:
        if flat.get(RESOURCE_NAME_TAG_KEY, "") != resource_name:
            rtnval = False
            return rtnval
    if resource_kind is not None:
        if flat.get(RESOURCE_KIND_TAG_KEY, "") != resource_kind:
            rtnval = False
            return rtnval
    rtnval = True
    return rtnval


class MetalApplyStages:
    """
        Owner-tagged, read-before-create apply stages for the Equinix Metal
        venue.

        Equinix Metal is a bare-metal venue.  The unit of provisioning is a
        Device (a physical server); provisioning latency is measured in
        minutes, so the device stage offers an aspects-controlled polling
        wait for the device to reach the ``active`` state.

        Every stage looks resources up by the owner tag-pair plus the run-id
        tag before creating, which is what makes ``apply ∘ apply`` idempotent.
    """

    def __init__(self, *, client: MetalClient, resolver: MetalResolver,
                 metro: str,
                 default_tags: Optional[Dict[str, str]] = None) -> None:
        """
            Construct a MetalApplyStages.

            :param client: The MetalClient.
            :param resolver: The MetalResolver.
            :param metro: The default metro slug.
            :param default_tags: Optional venue default tags.
        """
        self._client: MetalClient = client
        self._resolver: MetalResolver = resolver
        self._metro: str = metro
        self._default_tags: Dict[str, str] = (
            dict(default_tags) if default_tags is not None else {}
        )
        self._renderer: MetalUserDataRenderer = MetalUserDataRenderer()
        return

    # ------------------------------------------------------------------
    # VLAN (CloudNetwork)
    # ------------------------------------------------------------------

    def find_vlan(self, *, run_id: str,
                  name: str) -> Optional[Dict[str, Any]]:
        """
            Find an owned VLAN by run-id + resource-name tags.

            :param run_id: Run identifier.
            :param name: Neutral network name.

            :returns: A VLAN dict or None.
        """
        for vlan in self._client.list_vlans():
            tags = vlan.get("tags", [])
            if _owned_by(tag_strings=tags, run_id=run_id,
                         resource_name=name, resource_kind="network"):
                rtnval: Optional[Dict[str, Any]] = vlan
                return rtnval
        rtnval = None
        return rtnval

    def ensure_vlan(self, *, desired: CloudNetwork, run_id: str,
                    aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for a project VLAN.

            :param desired: Desired CloudNetwork.
            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: A ProvisionedResource.
        """
        existing = self.find_vlan(run_id=run_id, name=desired.name)
        if existing is not None:
            rtnval = self._vlan_resource(vlan=existing, name=desired.name)
            return rtnval

        neutral_tags = base_resource_tags(
            run_id=run_id, resource_name=desired.name,
            resource_kind="network", extra=dict(desired.tags),
            defaults=self._default_tags,
        )
        tag_strings = MetalTagTranslator.to_metal(neutral_tags=neutral_tags)
        created = self._client.create_vlan(
            metro=self._metro,
            description="automojo:{}:{}".format(run_id, desired.name),
            tags=tag_strings,
        )
        rtnval = self._vlan_resource(vlan=created, name=desired.name)
        return rtnval

    def _vlan_resource(self, *, vlan: Dict[str, Any],
                       name: str) -> ProvisionedResource:
        """
            Build a ProvisionedResource for a VLAN dict.

            :param vlan: VLAN dict.
            :param name: Neutral network name.

            :returns: A ProvisionedResource.
        """
        attributes: Dict[str, Any] = {}
        attributes["vlan_id"] = vlan.get("id", "")
        attributes["vxlan"] = vlan.get("vxlan", "")
        attributes["metro"] = vlan.get("metro", self._metro)
        rtnval = ProvisionedResource(
            kind="network", name=name,
            venue_id=str(vlan.get("id", "")),
            attributes=attributes,
            tags=MetalTagTranslator.from_metal(strings=vlan.get("tags", [])),
        )
        return rtnval

    # ------------------------------------------------------------------
    # IP reservation (CloudSubnet)
    # ------------------------------------------------------------------

    def find_ip_reservation(self, *, run_id: str,
                            name: str) -> Optional[Dict[str, Any]]:
        """
            Find an owned IP reservation by run-id + resource-name tags.

            :param run_id: Run identifier.
            :param name: Neutral subnet name.

            :returns: An IP-reservation dict or None.
        """
        for reservation in self._client.list_ip_reservations():
            tags = reservation.get("tags", [])
            if _owned_by(tag_strings=tags, run_id=run_id,
                         resource_name=name, resource_kind="subnet"):
                rtnval: Optional[Dict[str, Any]] = reservation
                return rtnval
        rtnval = None
        return rtnval

    def ensure_ip_reservation(self, *, desired: CloudSubnet, run_id: str,
                              aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for an IP reservation.

            :param desired: Desired CloudSubnet.
            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: A ProvisionedResource.
        """
        existing = self.find_ip_reservation(run_id=run_id, name=desired.name)
        if existing is not None:
            rtnval = self._ip_resource(reservation=existing,
                                       name=desired.name)
            return rtnval

        neutral_tags = base_resource_tags(
            run_id=run_id, resource_name=desired.name,
            resource_kind="subnet", extra=dict(desired.tags),
            defaults=self._default_tags,
        )
        tag_strings = MetalTagTranslator.to_metal(neutral_tags=neutral_tags)
        ip_type = "public_ipv4" if desired.public is True else "private_ipv4"
        created = self._client.create_ip_reservation(
            metro=self._metro, quantity=1, ip_type=ip_type,
            tags=tag_strings,
        )
        rtnval = self._ip_resource(reservation=created, name=desired.name)
        return rtnval

    def _ip_resource(self, *, reservation: Dict[str, Any],
                     name: str) -> ProvisionedResource:
        """
            Build a ProvisionedResource for an IP-reservation dict.

            :param reservation: IP-reservation dict.
            :param name: Neutral subnet name.

            :returns: A ProvisionedResource.
        """
        attributes: Dict[str, Any] = {}
        attributes["reservation_id"] = reservation.get("id", "")
        attributes["address"] = reservation.get("address", "")
        attributes["cidr"] = reservation.get("cidr", "")
        attributes["ip_type"] = reservation.get("type", "")
        rtnval = ProvisionedResource(
            kind="subnet", name=name,
            venue_id=str(reservation.get("id", "")),
            attributes=attributes,
            tags=MetalTagTranslator.from_metal(
                strings=reservation.get("tags", [])
            ),
        )
        return rtnval

    # ------------------------------------------------------------------
    # SSH key (CloudKeyPair)
    # ------------------------------------------------------------------

    def find_ssh_key(self, *, run_id: str,
                     name: str) -> Optional[Dict[str, Any]]:
        """
            Find an owned SSH key by run-id + resource-name tags or by
            label.

            :param run_id: Run identifier.
            :param name: Neutral key-pair name.

            :returns: An SSH-key dict or None.
        """
        expected_label = "automojo:{}:{}".format(run_id, name)
        for ssh_key in self._client.list_ssh_keys():
            if ssh_key.get("label", "") == expected_label:
                rtnval: Optional[Dict[str, Any]] = ssh_key
                return rtnval
            tags = ssh_key.get("tags", [])
            if _owned_by(tag_strings=tags, run_id=run_id,
                         resource_name=name, resource_kind="keypair"):
                rtnval = ssh_key
                return rtnval
        rtnval = None
        return rtnval

    def ensure_ssh_key(self, *, desired: CloudKeyPair, run_id: str,
                       aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for a project SSH key.

            :param desired: Desired CloudKeyPair.
            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: A ProvisionedResource.
        """
        existing = self.find_ssh_key(run_id=run_id, name=desired.name)
        if existing is not None:
            rtnval = self._ssh_key_resource(ssh_key=existing,
                                            name=desired.name)
            return rtnval

        label = "automojo:{}:{}".format(run_id, desired.name)
        created = self._client.create_ssh_key(
            label=label, key=desired.public_key_material,
        )
        rtnval = self._ssh_key_resource(ssh_key=created, name=desired.name)
        return rtnval

    def _ssh_key_resource(self, *, ssh_key: Dict[str, Any],
                          name: str) -> ProvisionedResource:
        """
            Build a ProvisionedResource for an SSH-key dict.

            :param ssh_key: SSH-key dict.
            :param name: Neutral key-pair name.

            :returns: A ProvisionedResource.
        """
        attributes: Dict[str, Any] = {}
        attributes["ssh_key_id"] = ssh_key.get("id", "")
        attributes["fingerprint"] = ssh_key.get("fingerprint", "")
        attributes["label"] = ssh_key.get("label", "")
        rtnval = ProvisionedResource(
            kind="keypair", name=name,
            venue_id=str(ssh_key.get("id", "")),
            attributes=attributes,
            tags=MetalTagTranslator.from_metal(
                strings=ssh_key.get("tags", [])
            ),
        )
        return rtnval

    # ------------------------------------------------------------------
    # Device (CloudInstance)
    # ------------------------------------------------------------------

    def find_device(self, *, run_id: str,
                    name: str) -> Optional[Dict[str, Any]]:
        """
            Find an owned device by run-id + resource-name tags.

            :param run_id: Run identifier.
            :param name: Neutral instance name.

            :returns: A device dict or None.
        """
        for device in self._client.list_devices():
            tags = device.get("tags", [])
            if _owned_by(tag_strings=tags, run_id=run_id,
                         resource_name=name, resource_kind="instance"):
                rtnval: Optional[Dict[str, Any]] = device
                return rtnval
        rtnval = None
        return rtnval

    def ensure_device(self, *, desired: CloudInstance, run_id: str,
                      ssh_key_ids: List[str], authkey: Optional[str],
                      aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for a Device (bare-metal server).

            Provisioning a bare-metal Device is slow; after create the stage
            polls the device until it reaches ``active`` using the aspects'
            ``verify_timeout`` / ``verify_interval`` bounds.

            :param desired: Desired CloudInstance.
            :param run_id: Run identifier.
            :param ssh_key_ids: Project SSH-key ids to install.
            :param authkey: Pre-minted VPN authkey (when vpn_join is set).
            :param aspects: Aspects.

            :returns: A ProvisionedResource.
            :raises: MetalCapacityError
        """
        existing = self.find_device(run_id=run_id, name=desired.name)
        if existing is not None:
            rtnval = self._device_resource(device=existing,
                                           name=desired.name)
            return rtnval

        accelerator_models: List[str] = []
        accelerators = desired.accelerators if desired.accelerators is not None else []
        for accelerator in accelerators:
            accelerator_models.append(accelerator.model)

        plan = self._resolver.size_to_plan(
            size_hint=desired.size, accelerators=accelerator_models,
            metro=self._metro,
        )
        os_slug = self._resolver.image_to_os_slug(
            family=desired.image.family, version=desired.image.version,
            arch=desired.image.architecture,
        )

        userdata = self._renderer.render(
            instance=desired,
            authkey=authkey if authkey is not None else "PLACEHOLDER",
        )

        neutral_tags = base_resource_tags(
            run_id=run_id, resource_name=desired.name,
            resource_kind="instance", extra=dict(desired.tags),
            defaults=self._default_tags,
        )
        if desired.vpn_join is not None:
            neutral_tags[VPN_PROVIDER_TAG_KEY] = desired.vpn_join.provider
        tag_strings = MetalTagTranslator.to_metal(neutral_tags=neutral_tags)

        created = self._client.create_device(
            hostname=desired.name, plan=plan, metro=self._metro,
            operating_system=os_slug, userdata=userdata,
            project_ssh_keys=list(ssh_key_ids), tags=tag_strings,
        )

        active = self._wait_for_active(
            device=created, instance_name=desired.name, aspects=aspects,
        )

        resource = self._device_resource(device=active, name=desired.name)
        resource.attributes["plan"] = plan
        resource.attributes["operating_system"] = os_slug
        if len(userdata) > 0:
            resource.attributes["userdata_present"] = True
        rtnval = resource
        return rtnval

    def reconcile_device(self, *, desired: CloudInstance, run_id: str,
                         aspects: Any) -> Optional[ProvisionedResource]:
        """
            Reconcile a live owned Device against the spec, realising a
            tag-only drift in place via the Metal API.

            Equinix Metal device tags are mutable; a tag drift is realised
            with ``update_device_tags`` (``PUT /devices/{id}``) with no
            reprovisioning of the bare-metal server.  A tag update is
            non-disruptive, so it is not gated behind ``aspects.confirm``.

            A hostname drift is *not* reconciled here — renaming a Metal
            device requires reprovisioning (UPDATE-by-recreate) and is left
            for the caller to handle.

            :param desired: Desired CloudInstance.
            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: A ProvisionedResource when the device tags were
                updated in place; ``None`` when the device was already in
                tag-shape (or only a non-tag drift exists).
        """
        existing = self.find_device(run_id=run_id, name=desired.name)
        if existing is None:
            rtnval: Optional[ProvisionedResource] = None
            return rtnval

        observed_hostname = existing.get("hostname", "")
        if observed_hostname != desired.name:
            rtnval = None
            return rtnval

        observed_tags = MetalTagTranslator.flat_dict(
            strings=existing.get("tags", [])
        )
        drifted = False
        for key, value in desired.tags.items():
            if observed_tags.get(key, None) != value:
                drifted = True
                break

        if drifted is not True:
            rtnval = None
            return rtnval

        neutral_tags = base_resource_tags(
            run_id=run_id, resource_name=desired.name,
            resource_kind="instance", extra=dict(desired.tags),
            defaults=self._default_tags,
        )
        if desired.vpn_join is not None:
            neutral_tags[VPN_PROVIDER_TAG_KEY] = desired.vpn_join.provider
        existing_vpn_device_id = observed_tags.get(VPN_DEVICE_ID_TAG_KEY,
                                                   None)
        if existing_vpn_device_id is not None and len(
                existing_vpn_device_id) > 0:
            neutral_tags[VPN_DEVICE_ID_TAG_KEY] = existing_vpn_device_id
        tag_strings = MetalTagTranslator.to_metal(neutral_tags=neutral_tags)

        device_id = str(existing.get("id", ""))
        updated = self._client.update_device_tags(
            device_id=device_id, tags=tag_strings,
        )
        rtnval = self._device_resource(device=updated, name=desired.name)
        return rtnval

    def _wait_for_active(self, *, device: Dict[str, Any],
                         instance_name: str,
                         aspects: Any) -> Dict[str, Any]:
        """
            Poll the device until it reaches ``active`` within the
            aspects-controlled bounds.

            :param device: The freshly-created device dict.
            :param instance_name: Neutral instance name (for errors).
            :param aspects: Aspects controlling timeout / interval.

            :returns: The device dict in its latest observed state.
            :raises: MetalCapacityError
        """
        state = device.get("state", "")
        if state in _ACTIVE_DEVICE_STATES:
            rtnval = device
            return rtnval

        timeout = float(_aspect_attr(aspects=aspects, name="verify_timeout",
                                     default=600.0))
        interval = float(_aspect_attr(aspects=aspects, name="verify_interval",
                                      default=10.0))
        device_id = str(device.get("id", ""))
        deadline = time.monotonic() + timeout
        latest = device

        while time.monotonic() < deadline:
            latest = self._client.get_device(device_id=device_id)
            state = latest.get("state", "")
            if state in _ACTIVE_DEVICE_STATES:
                rtnval = latest
                return rtnval
            if state in _TERMINAL_FAILURE_STATES:
                err_msg_lines = [
                    "Equinix Metal device provisioning failed."
                ]
                err_msg_lines.append("INSTANCE: {}".format(instance_name))
                err_msg_lines.append("DEVICE_ID: {}".format(device_id))
                err_msg_lines.append("STATE: {}".format(state))
                err_msg = os.linesep.join(err_msg_lines)
                raise MetalCapacityError(err_msg)
            time.sleep(interval)

        # The bound was exceeded — control reverts to the caller with a
        # typed exception rather than blocking indefinitely.
        err_msg_lines = [
            "Equinix Metal device did not reach 'active' before the "
            "verify_timeout bound elapsed."
        ]
        err_msg_lines.append("INSTANCE: {}".format(instance_name))
        err_msg_lines.append("DEVICE_ID: {}".format(device_id))
        err_msg_lines.append("LAST_STATE: {}".format(
            latest.get("state", "")
        ))
        err_msg_lines.append("TIMEOUT_SECONDS: {}".format(timeout))
        err_msg = os.linesep.join(err_msg_lines)
        raise MetalCapacityError(err_msg)

    def _device_resource(self, *, device: Dict[str, Any],
                         name: str) -> ProvisionedResource:
        """
            Build a ProvisionedResource for a device dict.

            :param device: Device dict.
            :param name: Neutral instance name.

            :returns: A ProvisionedResource.
        """
        attributes: Dict[str, Any] = {}
        attributes["device_id"] = device.get("id", "")
        attributes["state"] = device.get("state", "")
        attributes["hostname"] = device.get("hostname", "")
        attributes["plan"] = device.get("plan", "")
        attributes["metro"] = device.get("metro", self._metro)

        addresses = device.get("ip_addresses", [])
        for entry in addresses:
            if entry.get("public", False) is True:
                attributes["public_ip"] = entry.get("address", "")
            else:
                attributes["private_ip"] = entry.get("address", "")

        flat = MetalTagTranslator.flat_dict(strings=device.get("tags", []))
        vpn_device_id = flat.get(VPN_DEVICE_ID_TAG_KEY, None)
        if vpn_device_id is not None and len(vpn_device_id) > 0:
            attributes["vpn_device_id"] = vpn_device_id

        rtnval = ProvisionedResource(
            kind="instance", name=name,
            venue_id=str(device.get("id", "")),
            attributes=attributes,
            tags=MetalTagTranslator.from_metal(
                strings=device.get("tags", [])
            ),
        )
        return rtnval
