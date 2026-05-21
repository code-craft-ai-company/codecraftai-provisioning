"""
    .. module:: landscapeemitter
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Emit a landscape.yaml block from per-venue inventory.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import logging

from typing import Any, Dict, List, Optional

from automojo.provisioning.model.cloud.preemptionpolicy import PreemptionPolicy
from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.landscape.deviceaddressblock import (
    DeviceAddressBlock
)


logger = logging.getLogger(__name__)


class LandscapeEmitter:
    """
        Emit a landscape.yaml-compatible dict from per-venue inventory.

        The emitter is the last pipeline stage's worker.  It only filters
        instances (kind == "instance"), builds a DeviceAddressBlock per
        host, and shapes the surrounding ``apod`` / ``environment`` /
        ``vpn`` blocks from the spec.
    """

    def __init__(self, *, spec: Dict[str, Any],
                 inventory: Dict[str, List[ProvisionedResource]],
                 control_planes: Optional[Dict[str, Any]] = None) -> None:
        """
            Construct a LandscapeEmitter.

            :param spec: Normalised input spec dict (used for apod, venues,
                         vpn-provider details, group membership).
            :param inventory: Per-venue lists of ProvisionedResource.
            :param control_planes: Optional map provider-name ->
                                   IVPNControlPlane.  Not required when no
                                   instance carries vpn_join.
        """
        self._spec: Dict[str, Any] = spec
        self._inventory: Dict[str, List[ProvisionedResource]] = inventory
        self._control_planes: Dict[str, Any] = (
            control_planes if control_planes is not None else {}
        )
        return

    def emit(self, *, aspects: Any) -> Dict[str, Any]:
        """
            Build and return the landscape.yaml dict.

            :param aspects: Aspects (currently unused; reserved for overlay
                            query timeouts).

            :returns: A dict ready to be ``yaml.safe_dump``'d.
        """
        device_entries: List[Dict[str, Any]] = []

        instance_specs = self._instance_spec_index()
        groups_index = self._groups_index()
        cached_devices: Dict[str, List[Dict[str, Any]]] = {}

        any_vpn_join = False

        for venue_name, resources in self._inventory.items():
            for resource in resources:
                if resource.kind != "instance":
                    continue

                ispec = instance_specs.get(resource.name, {})
                vpn_join = ispec.get("vpn_join", None)

                block = DeviceAddressBlock(
                    public=resource.attributes.get("public_ip", None),
                    private=resource.attributes.get("private_ip", None),
                    overlay=self._resolve_overlay(
                        vpn_join=vpn_join,
                        instance_name=resource.name,
                        aspects=aspects,
                        cached_devices=cached_devices,
                    ),
                )

                if vpn_join is not None:
                    any_vpn_join = True

                entry: Dict[str, Any] = {
                    "name": resource.name,
                    "venue": venue_name,
                    "addresses": block.to_emitted_dict(),
                    "tags": list(resource.tags),
                    "preemption_policy": self._resolve_policy(
                        resource=resource, instance_spec=ispec,
                    ),
                }
                group = groups_index.get(resource.name, None)
                if group is not None:
                    entry["group"] = group

                device_entries.append(entry)

        rtnval: Dict[str, Any] = {
            "apod": {
                "name": self._spec.get("apod", {}).get("name", "unnamed"),
                "devices": device_entries,
            },
            "environment": {
                "venues": list(self._spec.get("venues", [])),
            },
            "pod": self._spec.get("pod", {}),
        }

        if any_vpn_join is True:
            rtnval["vpn"] = self._build_vpn_block()

        return rtnval

    def _resolve_policy(self, *, resource: ProvisionedResource,
                        instance_spec: Dict[str, Any]) -> str:
        """
            Resolve the preemption policy for an emitted device entry.

            The policy is read from the ProvisionedResource when the venue
            threaded it through; otherwise it falls back to the instance
            spec, and finally to the fail-loud default.

            :param resource: The ProvisionedResource for the device.
            :param instance_spec: The matching instance spec dict.

            :returns: A PreemptionPolicy value string.
        """
        from_resource = getattr(resource, "preemption_policy", None)
        if from_resource is not None and len(str(from_resource)) > 0:
            rtnval = str(from_resource)
            return rtnval

        from_spec = instance_spec.get("preemption_policy", None)
        if from_spec is not None and len(str(from_spec)) > 0:
            rtnval = str(from_spec)
            return rtnval

        rtnval = PreemptionPolicy.FAIL.value
        return rtnval

    def _instance_spec_index(self) -> Dict[str, Dict[str, Any]]:
        """
            Build an index from instance-name -> instance-spec dict.

            :returns: Index keyed by instance name.
        """
        rtnval: Dict[str, Dict[str, Any]] = {}
        for entry in self._spec.get("instances", []):
            rtnval[entry["name"]] = entry
        return rtnval

    def _groups_index(self) -> Dict[str, str]:
        """
            Build an index from instance-name -> group-name.

            :returns: Index of instance name to group name.
        """
        rtnval: Dict[str, str] = {}
        for group in self._spec.get("groups", []):
            name = group.get("name", "")
            for member in group.get("members", []):
                rtnval[member] = name
        return rtnval

    def _resolve_overlay(self, *, vpn_join: Any, instance_name: str,
                         aspects: Any,
                         cached_devices: Dict[str, List[Dict[str, Any]]]
                         ) -> Optional[Dict[str, Any]]:
        """
            Look up the overlay block for an instance, if any.

            :param vpn_join: VPN-join dict (or None).
            :param instance_name: Logical instance name.
            :param aspects: Aspects.
            :param cached_devices: Per-emit cache of list_devices results.

            :returns: Overlay dict or None.
        """
        if vpn_join is None:
            rtnval: Optional[Dict[str, Any]] = None
            return rtnval

        provider = vpn_join.get("provider") if isinstance(vpn_join, dict) else getattr(vpn_join, "provider", None)
        if provider is None:
            rtnval = None
            return rtnval

        control_plane = self._control_planes.get(provider, None)
        if control_plane is None:
            rtnval = None
            return rtnval

        if provider not in cached_devices:
            try:
                cached_devices[provider] = control_plane.list_devices(
                    aspects=aspects
                )
            except (RuntimeError, OSError) as xcpt:
                # A transport / runtime failure querying the control plane is
                # non-fatal for landscape emission -- the overlay block is
                # simply omitted. A SchemaSemanticError is not caught here;
                # it must bubble.
                logger.warning(
                    "Overlay query failed for provider=%r: %s",
                    provider, xcpt,
                )
                cached_devices[provider] = []

        for device in cached_devices[provider]:
            if device.get("hostname") == instance_name:
                rtnval = {
                    "provider": provider,
                    "address": device.get("address", ""),
                    "magic_dns": device.get("magic_dns", ""),
                }
                return rtnval

        rtnval = None
        return rtnval

    def _build_vpn_block(self) -> Dict[str, Any]:
        """
            Build the top-level ``vpn:`` block.

            :returns: VPN providers block.
        """
        providers: List[Dict[str, Any]] = []
        for entry in self._spec.get("vpn_providers", []):
            providers.append(entry)
        rtnval = {"providers": providers}
        return rtnval
