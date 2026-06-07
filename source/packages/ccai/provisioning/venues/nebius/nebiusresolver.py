"""
    .. module:: nebiusresolver
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: NebiusResolver — image-id and preset-slug resolution for the
        Nebius venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import List, Optional

from ccai.provisioning.model.cloud.cloudacceleratorcatalog import (
    CloudAcceleratorCatalog
)
from ccai.provisioning.model.cloud.cloudinstancesizecatalog import (
    CloudInstanceSizeCatalog
)
from ccai.provisioning.model.cloud.cloudacceleratorspec import (
    CloudAcceleratorSpec
)
from ccai.provisioning.model.cloud.cloudinterconnect import (
    CloudInterconnect
)
from ccai.provisioning.model.exceptions import SchemaSemanticError
from ccai.provisioning.venues.nebius.nebiuserrors import (
    NebiusValidationError
)


# Nebius platforms that expose an IB-eligible GPU Cluster.  A platform not in
# this set cannot be placed into a GPU Cluster (IB-enabled placement group).
IB_ELIGIBLE_PLATFORMS = frozenset({
    "gpu-h100-sxm", "gpu-h200-sxm", "gpu-h200-nvl", "gpu-b200-sxm",
})


class NebiusResolver:
    """
        Resolver for Nebius image identifiers and instance preset slugs.

        Image resolution maps a neutral ``(family, version, architecture)``
        tuple onto a Nebius image id.  Preset resolution maps a neutral size
        hint plus an optional accelerator list onto a Nebius platform/preset
        slug via the :class:`CloudAcceleratorCatalog`.
    """

    VENUE_NAME = "nebius"

    def __init__(self, *, catalog: CloudAcceleratorCatalog) -> None:
        """
            Construct a NebiusResolver.

            :param catalog: The accelerator catalog used for SKU resolution.
        """
        self._catalog: CloudAcceleratorCatalog = catalog
        return

    def image_to_id(self, *, family: str, version: str,
                     architecture: str) -> str:
        """
            Resolve a neutral image tuple into a Nebius image identifier.

            Nebius image ids follow a deterministic family/version/arch
            naming convention so the resolution is a pure mapping.

            :param family: The image family (e.g. ``ubuntu``).
            :param version: The image version (e.g. ``22.04``).
            :param architecture: The CPU architecture (e.g. ``x86_64``).

            :returns: A Nebius image identifier string.

            :raises: NebiusValidationError when any component is empty.
        """
        if family is None or len(family) == 0:
            raise NebiusValidationError("image family must not be empty.")
        if version is None or len(version) == 0:
            raise NebiusValidationError("image version must not be empty.")
        if architecture is None or len(architecture) == 0:
            raise NebiusValidationError(
                "image architecture must not be empty."
            )

        version_slug = version.replace(".", "-")
        rtnval = "img-{}-{}-{}".format(family, version_slug, architecture)
        return rtnval

    def size_to_preset(self, *, size_hint: str,
                       accelerators: Optional[List[CloudAcceleratorSpec]] = None,
                       interconnect: Optional[CloudInterconnect] = None) -> str:
        """
            Resolve a neutral size hint into a Nebius platform/preset slug.

            When an accelerator list is supplied, the first accelerator's
            neutral model name is resolved through the catalog to its Nebius
            SKU and that SKU becomes the preset slug.  Otherwise the size
            hint is used verbatim as a CPU-preset slug.

            :param size_hint: The neutral size identifier.
            :param accelerators: Optional list of CloudAcceleratorSpec.
            :param interconnect: Optional CloudInterconnect (informational
                here; IB-eligibility is checked separately).

            :returns: The resolved Nebius preset slug.

            :raises: NebiusValidationError when the accelerator is not on
                the Nebius venue.
        """
        size_catalog = CloudInstanceSizeCatalog.default()
        native = size_catalog.resolve(token=size_hint, venue=self.VENUE_NAME)
        effective = native if native is not None else size_hint
        size_hint = effective

        effective_accelerators = accelerators if accelerators is not None else []

        if len(effective_accelerators) > 0:
            first = effective_accelerators[0]
            try:
                sku = self._catalog.resolve(neutral_name=first.model,
                                            venue=self.VENUE_NAME)
            except SchemaSemanticError as xcpt:
                err_msg_lines = [
                    "Accelerator is not available on the Nebius venue."
                ]
                err_msg_lines.append("MODEL: {}".format(first.model))
                err_msg_lines.append("CAUSE: {}".format(xcpt))
                err_msg = os.linesep.join(err_msg_lines)
                raise NebiusValidationError(err_msg) from None
            rtnval = sku
            return rtnval

        if size_hint is None or len(size_hint) == 0:
            raise NebiusValidationError(
                "size_hint must not be empty when no accelerators are set."
            )
        rtnval = size_hint
        return rtnval

    def platform_for_preset(self, *, preset: str) -> str:
        """
            Derive the Nebius compute platform identifier from a preset slug.

            Nebius GPU preset slugs carry a leading ``gpu-<model>-<topology>``
            platform stem followed by a numeric count suffix; the platform is
            the slug with the trailing ``-<count>`` segment removed when that
            segment is purely numeric.

            :param preset: The Nebius preset slug.

            :returns: The Nebius platform identifier.
        """
        parts = preset.rsplit("-", 1)
        if len(parts) == 2 and parts[1].isdigit():
            rtnval = parts[0]
            return rtnval
        rtnval = preset
        return rtnval

    def is_ib_eligible(self, *, platform: str) -> bool:
        """
            Return whether a Nebius platform supports GPU-Cluster (IB)
            placement.

            :param platform: The Nebius platform identifier.

            :returns: ``True`` when the platform is IB-eligible.
        """
        rtnval = platform in IB_ELIGIBLE_PLATFORMS
        return rtnval
