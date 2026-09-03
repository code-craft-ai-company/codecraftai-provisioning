"""
    .. module:: crusoeresolver
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: CrusoeResolver — neutral image / size / interconnect resolution
        to Crusoe Cloud aliases and instance types.

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
from ccai.interfaces.cloudacceleratorspec import (
    CloudAcceleratorSpec
)
from ccai.provisioning.model.cloud.cloudinterconnect import CloudInterconnect
from ccai.provisioning.model.cloud.imagefamily import normalize_family
from ccai.interfaces.schemasemanticerror import SchemaSemanticError
from ccai.provisioning.model.cloud.imagefamilynotofferederror import (
    ImageFamilyNotOfferedOnVenueError
)


VENUE_NAME = "crusoe"

# Crusoe image family aliases keyed by neutral family name.  Crusoe boots
# instances from a documented image alias rather than an opaque id.
_IMAGE_FAMILY_ALIASES = {
    "ubuntu": "ubuntu",
    "debian": "debian",
    "rhel": "rhel",
    "fedora": "fedora",
}

# Crusoe interconnect kinds the venue accepts.  The neutral INFINIBAND_*
# family maps onto a Crusoe IB partition; ETHERNET maps onto plain placement.
_IB_INTERCONNECT_KINDS = frozenset({
    "INFINIBAND_HDR", "INFINIBAND_NDR", "INFINIBAND_XDR"
})

# Crusoe instance-type substrings that designate an IB-eligible SKU.  The
# 8x SXM5/SXM GPU SKUs are the ones Crusoe places on an InfiniBand fabric.
_IB_ELIGIBLE_MARKERS = ("sxm5.8x", "sxm.8x", "nvl.8x")


class CrusoeResolver:
    """
        Resolves neutral image / size / interconnect requests onto Crusoe
        Cloud aliases and instance types using the accelerator catalog.
    """

    def __init__(self, *, catalog: CloudAcceleratorCatalog) -> None:
        """
            Construct a CrusoeResolver.

            :param catalog: The accelerator catalog used for SKU resolution.
        """
        self._catalog: CloudAcceleratorCatalog = catalog
        return

    def image_to_alias(self, *, family: str, version: str,
                       arch: str) -> str:
        """
            Resolve a neutral image triple to a Crusoe image alias.

            :param family: The neutral image family.
            :param version: The neutral image version.
            :param arch: The neutral image architecture.

            :returns: The Crusoe image alias string.

            :raises: SchemaSemanticError when the family is unsupported.
        """
        canonical_family = normalize_family(value=family)
        family_token = canonical_family.value
        base = _IMAGE_FAMILY_ALIASES.get(family_token, None)
        if base is None:
            err_msg_lines = ["The crusoe venue does not support the image "
                             "family."]
            err_msg_lines.append("VENUE: crusoe")
            err_msg_lines.append("FAMILY: {}".format(family_token))
            err_msg_lines.append("SUPPORTED: {}".format(
                ", ".join(sorted(_IMAGE_FAMILY_ALIASES.keys()))))
            err_msg = os.linesep.join(err_msg_lines)
            # The family normalised to a real ImageFamily member that this venue
            # cannot serve: a validation finding about a spec/venue pairing, so it
            # is an ordinary ValueError a validator may aggregate.  A family that
            # does not normalise at all already raised SchemaSemanticError above,
            # which halts because the spec then names something that does not exist.
            raise ImageFamilyNotOfferedOnVenueError(err_msg)

        rtnval = "{0}-{1}-{2}".format(base, version, arch)
        return rtnval

    def size_to_instance_type(self, *, size_hint: str,
                              accelerators: Optional[List[CloudAcceleratorSpec]],
                              interconnect: Optional[CloudInterconnect]) -> str:
        """
            Resolve a neutral size hint plus accelerators into a Crusoe
            instance type.

            When the instance carries accelerators the first accelerator's
            catalog name is resolved to the Crusoe SKU; otherwise the raw
            ``size_hint`` is used directly.

            :param size_hint: The neutral size hint.
            :param accelerators: Optional list of CloudAcceleratorSpec.
            :param interconnect: Optional CloudInterconnect (unused for
                resolution; consulted by the validator).

            :returns: The Crusoe instance type string.

            :raises: SchemaSemanticError when an accelerator is not on the
                Crusoe venue.
        """
        size_catalog = CloudInstanceSizeCatalog.default()
        native = size_catalog.resolve(token=size_hint, venue=VENUE_NAME)
        effective = native if native is not None else size_hint
        size_hint = effective

        accel_list = accelerators if accelerators is not None else []
        if len(accel_list) > 0:
            first = accel_list[0]
            sku = self._catalog.resolve(neutral_name=first.model,
                                        venue=VENUE_NAME)
            rtnval = sku
            return rtnval

        if size_hint is None or len(size_hint) == 0:
            raise SchemaSemanticError(
                "Crusoe instance requires either a size hint or "
                "an accelerator spec."
            )

        rtnval = size_hint
        return rtnval

    def instance_type_supports_ib(self, *, instance_type: str) -> bool:
        """
            Report whether a Crusoe instance type supports IB placement.

            :param instance_type: The Crusoe instance type string.

            :returns: ``True`` when the SKU is IB-eligible.
        """
        rtnval = False
        if instance_type is not None:
            lowered = instance_type.lower()
            for marker in _IB_ELIGIBLE_MARKERS:
                if marker in lowered:
                    rtnval = True
                    break
        return rtnval

    def interconnect_is_infiniband(self, *,
                                   interconnect: Optional[CloudInterconnect]
                                   ) -> bool:
        """
            Report whether a neutral interconnect requests InfiniBand.

            :param interconnect: Optional CloudInterconnect.

            :returns: ``True`` when an INFINIBAND_* kind is requested.
        """
        rtnval = False
        if interconnect is not None:
            if interconnect.kind in _IB_INTERCONNECT_KINDS:
                rtnval = True
        return rtnval
