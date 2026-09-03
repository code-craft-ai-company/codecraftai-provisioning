"""
    .. module:: vultrresolver
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: VultrResolver — maps neutral image / size hints to Vultr ids.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Optional

from ccai.provisioning.model.cloud.cloudinstancesizecatalog import (
    CloudInstanceSizeCatalog
)
from ccai.interfaces.cloudacceleratorspec import (
    CloudAcceleratorSpec
)
from ccai.provisioning.model.cloud.imagefamily import normalize_family
from ccai.provisioning.model.cloud.imagefamilynotofferederror import (
    ImageFamilyNotOfferedOnVenueError
)
from ccai.provisioning.venues.vultr.vultrclient import VultrClient
from ccai.provisioning.venues.vultr.vultrerrors import VultrValidationError


# Minimal GPU SKU catalog Vultr publishes.  Maps a neutral accelerator model
# to a Vultr Cloud GPU plan id.  Vultr's GPU SKU set is small (single-node).
_GPU_PLAN_CATALOG: Dict[str, str] = {
    "A16": "vcg-a16-2c-8g-2vram",
    "A40": "vcg-a40-6c-32g-12vram",
    "L40S": "vcg-l40s-12c-64g-24vram",
}

# Canonical image family to OS-name substring used against ``GET /os``.
_OS_FAMILY_HINTS: Dict[str, str] = {
    "ubuntu": "Ubuntu",
    "debian": "Debian",
    "rhel": "Rocky Linux",
    "rocky": "Rocky Linux",
    "fedora": "Fedora",
    "almalinux": "AlmaLinux",
}


class VultrResolver:
    """
        Resolver translating neutral hints into Vultr identifiers.

        ``image_to_os_id`` consults ``GET /os``; ``size_to_plan`` maps size
        hints (and GPU accelerators) to a Vultr plan id.
    """

    def __init__(self, *, client: VultrClient) -> None:
        """
            Construct a VultrResolver.

            :param client: A VultrClient for API access.
        """
        self._client: VultrClient = client
        self._os_cache: Optional[List[Dict[str, Any]]] = None
        self._region_cache: Optional[List[Dict[str, Any]]] = None
        return

    def _load_os(self) -> List[Dict[str, Any]]:
        """
            Load and cache the Vultr OS catalog.

            :returns: A list of OS dicts.
        """
        if self._os_cache is None:
            self._os_cache = self._client.list_all(
                path="/os", collection_key="os"
            )
        rtnval = self._os_cache
        return rtnval

    def _load_regions(self) -> List[Dict[str, Any]]:
        """
            Load and cache the Vultr region catalog.

            :returns: A list of region dicts.
        """
        if self._region_cache is None:
            self._region_cache = self._client.list_all(
                path="/regions", collection_key="regions"
            )
        rtnval = self._region_cache
        return rtnval

    def region_is_known(self, *, region: str) -> bool:
        """
            Return whether a region slug resolves to a Vultr region.

            :param region: A candidate region slug.

            :returns: True when the region exists.
        """
        regions = self._load_regions()
        found = False
        for entry in regions:
            if entry.get("id", "") == region:
                found = True
        rtnval = found
        return rtnval

    def image_to_os_id(self, *, family: str, version: str,
                       arch: str) -> int:
        """
            Resolve a neutral image family/version to a Vultr ``os_id``.

            :param family: The OS family (ubuntu, debian, rhel, ...).
            :param version: The OS version string.
            :param arch: The CPU architecture hint.

            :returns: The integer Vultr ``os_id``.
            :raises: VultrValidationError, SchemaSemanticError
        """
        canonical_family = normalize_family(value=family)
        family_lower = canonical_family.value
        if family_lower not in _OS_FAMILY_HINTS:
            known = sorted(_OS_FAMILY_HINTS.keys())
            err_msg_lines = ["The vultr venue does not support the image "
                             "family."]
            err_msg_lines.append("VENUE: vultr")
            err_msg_lines.append("FAMILY: {}".format(family_lower))
            err_msg_lines.append("SUPPORTED: {}".format(", ".join(known)))
            err_msg = os.linesep.join(err_msg_lines)
            # The family normalised to a real ImageFamily member that this venue
            # cannot serve: a validation finding about a spec/venue pairing, so it
            # is an ordinary ValueError a validator may aggregate.  A family that
            # does not normalise at all already raised SchemaSemanticError above,
            # which halts because the spec then names something that does not exist.
            raise ImageFamilyNotOfferedOnVenueError(err_msg)

        name_hint = _OS_FAMILY_HINTS[family_lower]
        os_entries = self._load_os()

        candidates: List[Dict[str, Any]] = []
        for entry in os_entries:
            entry_name = entry.get("name", "")
            if name_hint in entry_name and version in entry_name:
                candidates.append(entry)

        if len(candidates) == 0:
            err_msg_lines = ["No Vultr OS matches the requested image."]
            err_msg_lines.append("FAMILY: {}".format(family))
            err_msg_lines.append("VERSION: {}".format(version))
            err_msg_lines.append("ARCH: {}".format(arch))
            err_msg = os.linesep.join(err_msg_lines)
            raise VultrValidationError(err_msg)

        chosen = candidates[0]
        rtnval = int(chosen.get("id", 0))
        return rtnval

    def size_to_plan(self, *, size_hint: str,
                     accelerators: Optional[List[CloudAcceleratorSpec]] = None
                     ) -> str:
        """
            Resolve a neutral size hint (and accelerators) to a Vultr plan id.

            When the instance carries a GPU accelerator the resolver returns
            the matching Vultr Cloud GPU plan id; otherwise the size hint is
            taken as the plan id directly (it is already a Vultr plan slug
            such as ``vc2-2c-4gb`` or ``vhf-*``).

            :param size_hint: The neutral instance size hint.
            :param accelerators: Optional list of CloudAcceleratorSpec.

            :returns: A Vultr plan id string.
            :raises: VultrValidationError
        """
        size_catalog = CloudInstanceSizeCatalog.default()
        native = size_catalog.resolve(token=size_hint, venue="vultr")
        effective = native if native is not None else size_hint
        size_hint = effective

        accel_list = accelerators if accelerators is not None else []
        if len(accel_list) > 0:
            first = accel_list[0]
            model = first.model
            if model not in _GPU_PLAN_CATALOG:
                known = sorted(_GPU_PLAN_CATALOG.keys())
                err_msg_lines = [
                    "Accelerator model is not available on Vultr."
                ]
                err_msg_lines.append("MODEL: {!r}".format(model))
                err_msg_lines.append("KNOWN: {}".format(", ".join(known)))
                err_msg = os.linesep.join(err_msg_lines)
                raise VultrValidationError(err_msg)
            rtnval = _GPU_PLAN_CATALOG[model]
            return rtnval

        if size_hint is None or len(size_hint) == 0:
            err_msg = (
                "VultrResolver.size_to_plan requires a non-empty size hint "
                "when no accelerators are present."
            )
            raise VultrValidationError(err_msg)

        rtnval = size_hint
        return rtnval

    @classmethod
    def accelerator_models(cls) -> List[str]:
        """
            Return the list of accelerator models known to the Vultr venue.

            :returns: A sorted list of model names.
        """
        rtnval = sorted(_GPU_PLAN_CATALOG.keys())
        return rtnval
