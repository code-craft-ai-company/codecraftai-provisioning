"""
    .. module:: linoderesolver
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LinodeResolver — maps neutral image families, sizes, and
               accelerator models onto Linode SDK identifiers.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Dict, List, Optional

from ccai.provisioning.model.cloud.cloudinstancesizecatalog import (
    CloudInstanceSizeCatalog
)
from ccai.provisioning.model.cloud.imagefamily import normalize_family
from ccai.provisioning.model.exceptions import SchemaSemanticError

from ccai.provisioning.venues.linode.linodeerrors import (
    LinodeValidationError
)


# Canonical image family -> Linode image id prefix.  Version is appended.
_IMAGE_FAMILY_MAP: Dict[str, str] = {
    "ubuntu": "linode/ubuntu",
    "debian": "linode/debian",
    "rhel": "linode/rhel",
    "fedora": "linode/fedora",
    "almalinux": "linode/almalinux",
    "rocky": "linode/rocky",
}

# Neutral size hint -> Linode type slug.  These map common neutral sizes
# onto Linode's published Standard / Dedicated CPU plans.
_SIZE_HINT_MAP: Dict[str, str] = {
    "small": "g6-standard-2",
    "medium": "g6-standard-4",
    "large": "g6-standard-6",
    "xlarge": "g6-standard-8",
    "t3.micro": "g6-nanode-1",
    "t3.small": "g6-standard-1",
    "t3.medium": "g6-standard-2",
    "dedicated-2": "g6-dedicated-2",
    "dedicated-4": "g6-dedicated-4",
}

# Neutral accelerator model -> Linode GPU type slug.  Linode publishes a
# minimal GPU catalog (RTX 4000 Ada and RTX 6000 classes).
_ACCELERATOR_MAP: Dict[str, str] = {
    "RTX4000": "g1-gpu-rtx4000-1",
    "RTX4000_ADA": "g2-gpu-rtx4000a1-s",
    "RTX6000": "g1-gpu-rtx6000-1",
    "RTX6000_2": "g1-gpu-rtx6000-2",
    "RTX6000_3": "g1-gpu-rtx6000-3",
    "RTX6000_4": "g1-gpu-rtx6000-4",
}

# Linode region slugs the venue accepts.
_KNOWN_REGIONS: frozenset = frozenset({
    "us-east", "us-central", "us-west", "us-southeast", "us-iad",
    "us-ord", "us-lax", "us-sea", "us-mia",
    "ca-central", "eu-west", "eu-central", "fr-par", "nl-ams",
    "gb-lon", "se-sto", "es-mad", "it-mil", "de-fra-2",
    "ap-south", "ap-northeast", "ap-southeast", "ap-west", "in-maa",
    "jp-osa", "id-cgk", "br-gru", "au-mel",
})


class LinodeResolver:
    """
        Resolver translating neutral model identifiers to Linode SDK ids.

        Linode is a mid-tier cloud; the resolver carries a small static
        catalog for images, instance types, and the limited GPU SKU set.
        It performs no network I/O.
    """

    def image_to_id(self, *, family: str, version: str,
                    architecture: str) -> str:
        """
            Resolve a neutral image family/version to a Linode image id.

            :param family: Neutral image family (``ubuntu``, ``debian``...).
            :param version: Image version string (``24.04``).
            :param architecture: Image architecture (informational).

            :returns: A Linode image id, e.g. ``linode/ubuntu24.04``.
            :raises: LinodeValidationError, SchemaSemanticError
        """
        canonical_family = normalize_family(value=family)
        normalized = canonical_family.value
        prefix = _IMAGE_FAMILY_MAP.get(normalized, None)
        if prefix is None:
            known = ", ".join(sorted(_IMAGE_FAMILY_MAP.keys()))
            err_msg_lines = ["The linode venue does not support the image "
                             "family."]
            err_msg_lines.append("VENUE: linode")
            err_msg_lines.append("SUPPORTED: {}".format(known))
            err_msg_lines.append("FAMILY: {}".format(normalized))
            err_msg = os.linesep.join(err_msg_lines)
            raise SchemaSemanticError(err_msg)

        compact_version = version.replace(".", "").replace("-", "")
        rtnval = "{}{}".format(prefix, compact_version)
        return rtnval

    def size_to_type(self, *, size_hint: str,
                     accelerators: Optional[List[str]] = None) -> str:
        """
            Resolve a neutral size (or accelerator model) to a Linode type.

            When an accelerator model is supplied it takes precedence and
            resolves to a Linode GPU plan slug.

            :param size_hint: Neutral size identifier.
            :param accelerators: Optional list of neutral accelerator models.

            :returns: A Linode type slug.
            :raises: LinodeValidationError
        """
        size_catalog = CloudInstanceSizeCatalog.default()
        native = size_catalog.resolve(token=size_hint, venue="linode")
        effective = native if native is not None else size_hint
        size_hint = effective

        effective_accelerators = accelerators if accelerators is not None else []
        if len(effective_accelerators) > 0:
            first_model = effective_accelerators[0]
            gpu_slug = self.accelerator_to_type(model=first_model)
            rtnval = gpu_slug
            return rtnval

        # A size hint already shaped like a Linode type slug passes through.
        if size_hint.startswith("g6-") or size_hint.startswith("g1-gpu-") \
                or size_hint.startswith("g2-gpu-"):
            rtnval = size_hint
            return rtnval

        mapped = _SIZE_HINT_MAP.get(size_hint, None)
        if mapped is None:
            known = ", ".join(sorted(_SIZE_HINT_MAP.keys()))
            err_msg_lines = ["Unknown size hint for the Linode venue."]
            err_msg_lines.append("KNOWN: {}".format(known))
            err_msg_lines.append("ACTUAL: {!r}".format(size_hint))
            err_msg = os.linesep.join(err_msg_lines)
            raise LinodeValidationError(err_msg)

        rtnval = mapped
        return rtnval

    def accelerator_to_type(self, *, model: str) -> str:
        """
            Resolve a neutral accelerator model to a Linode GPU type slug.

            :param model: Neutral accelerator model (``RTX6000``...).

            :returns: A Linode GPU type slug.
            :raises: LinodeValidationError
        """
        normalized = model.upper()
        slug = _ACCELERATOR_MAP.get(normalized, None)
        if slug is None:
            known = ", ".join(sorted(_ACCELERATOR_MAP.keys()))
            err_msg_lines = ["Accelerator model not in the Linode GPU catalog."]
            err_msg_lines.append("KNOWN: {}".format(known))
            err_msg_lines.append("ACTUAL: {!r}".format(model))
            err_msg = os.linesep.join(err_msg_lines)
            raise LinodeValidationError(err_msg)

        rtnval = slug
        return rtnval

    def is_known_region(self, *, region: str) -> bool:
        """
            Test whether a region resolves to a Linode region slug.

            :param region: Candidate region slug.

            :returns: True when the region is a known Linode region.
        """
        rtnval = region in _KNOWN_REGIONS
        return rtnval
