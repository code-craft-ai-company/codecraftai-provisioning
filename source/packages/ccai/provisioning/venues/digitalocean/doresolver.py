"""
    .. module:: doresolver
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: DoResolver — maps neutral image / size hints to DigitalOcean
               slugs.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Any, List, Optional

from ccai.provisioning.model.cloud.cloudinstancesizecatalog import (
    CloudInstanceSizeCatalog
)
from ccai.provisioning.model.cloud.imagefamily import normalize_family
from ccai.interfaces.schemasemanticerror import SchemaSemanticError
from ccai.provisioning.model.cloud.imagefamilynotofferederror import (
    ImageFamilyNotOfferedOnVenueError
)

from ccai.provisioning.venues.digitalocean.doerrors import (
    DoValidationError
)


# Image family + version -> DigitalOcean image slug.  Families are the
# canonical tokens from the shared image vocabulary.
_IMAGE_SLUGS = {
    ("ubuntu", "24.04"): "ubuntu-24-04-x64",
    ("ubuntu", "22.04"): "ubuntu-22-04-x64",
    ("ubuntu", "20.04"): "ubuntu-20-04-x64",
    ("debian", "12"): "debian-12-x64",
    ("debian", "11"): "debian-11-x64",
    ("fedora", "40"): "fedora-40-x64",
    ("rhel", "9"): "rockylinux-9-x64",
    ("rocky", "9"): "rockylinux-9-x64",
}

# Canonical image families the DigitalOcean resolver can serve.
_SUPPORTED_FAMILIES = frozenset(fam for (fam, ver) in _IMAGE_SLUGS)

# GPU accelerator model -> DigitalOcean GPU droplet size slug.
_GPU_SIZE_SLUGS = {
    ("H100", 1): "gpu-h100x1",
    ("H100", 8): "gpu-h100x8",
    ("H100_SXM", 1): "gpu-h100x1",
    ("H100_SXM", 8): "gpu-h100x8",
    ("H200", 1): "gpu-h200x1",
    ("H200", 8): "gpu-h200x8",
}


class DoResolver:
    """
        Resolves neutral image / size descriptors onto DigitalOcean slugs.

        DigitalOcean exposes a thin GPU catalog (single-node H100 / H200
        SKUs) and no high-bandwidth cluster interconnect; callers that ask
        for an unmapped GPU model receive a clear validate-error.
    """

    def __init__(self) -> None:
        """
            Construct a DoResolver.
        """
        return

    def image_to_slug(self, *, family: str, version: str,
                       architecture: str) -> str:
        """
            Resolve a neutral image family/version onto a DO image slug.

            :param family: Image family (e.g. ``ubuntu``).
            :param version: Image version (e.g. ``24.04``).
            :param architecture: Image architecture (e.g. ``x86_64``).

            :returns: A DigitalOcean image slug.
            :raises: DoValidationError, SchemaSemanticError
        """
        canonical_family = normalize_family(value=family)
        family_token = canonical_family.value

        if family_token not in _SUPPORTED_FAMILIES:
            supported = ", ".join(sorted(_SUPPORTED_FAMILIES))
            err_msg_lines = ["The digitalocean venue does not support the "
                             "image family."]
            err_msg_lines.append("VENUE: digitalocean")
            err_msg_lines.append("FAMILY: {}".format(family_token))
            err_msg_lines.append("SUPPORTED: {}".format(supported))
            err_msg = os.linesep.join(err_msg_lines)
            # The family normalised to a real ImageFamily member that this venue
            # cannot serve: a validation finding about a spec/venue pairing, so it
            # is an ordinary ValueError a validator may aggregate.  A family that
            # does not normalise at all already raised SchemaSemanticError above,
            # which halts because the spec then names something that does not exist.
            raise ImageFamilyNotOfferedOnVenueError(err_msg)

        key = (family_token, version)
        slug = _IMAGE_SLUGS.get(key, None)
        if slug is None:
            supported = sorted(
                "{}/{}".format(fam, ver) for (fam, ver) in _IMAGE_SLUGS
            )
            err_msg_lines = ["DigitalOcean has no image slug for the image."]
            err_msg_lines.append("FAMILY: {}".format(family_token))
            err_msg_lines.append("VERSION: {}".format(version))
            err_msg_lines.append("SUPPORTED: {}".format(", ".join(supported)))
            err_msg = os.linesep.join(err_msg_lines)
            raise DoValidationError(err_msg)

        if architecture not in ("x86_64", "amd64", "x64"):
            err_msg_lines = ["DigitalOcean droplet images are x86_64 only."]
            err_msg_lines.append("ARCHITECTURE: {}".format(architecture))
            err_msg = os.linesep.join(err_msg_lines)
            raise DoValidationError(err_msg)

        rtnval = slug
        return rtnval

    def size_to_slug(self, *, size_hint: str,
                     accelerators: Optional[List[Any]] = None) -> str:
        """
            Resolve a neutral size hint onto a DigitalOcean size slug.

            When ``accelerators`` is present the GPU SKU catalog is used and
            the GPU slug takes precedence over the size hint.

            :param size_hint: Neutral size identifier (already a DO slug or
                              a generic hint such as ``s-2vcpu-4gb``).
            :param accelerators: Optional list of CloudAcceleratorSpec.

            :returns: A DigitalOcean size slug.
            :raises: DoValidationError
        """
        size_catalog = CloudInstanceSizeCatalog.default()
        native = size_catalog.resolve(token=size_hint, venue="digitalocean")
        effective = native if native is not None else size_hint
        size_hint = effective

        effective_accels = accelerators if accelerators is not None else []
        if len(effective_accels) > 0:
            first = effective_accels[0]
            model = getattr(first, "model", "")
            count = getattr(first, "count", 1)
            gpu_slug = _GPU_SIZE_SLUGS.get((model, count), None)
            if gpu_slug is None:
                supported = sorted(set(_GPU_SIZE_SLUGS.values()))
                err_msg_lines = [
                    "DigitalOcean has no GPU droplet for the accelerator."
                ]
                err_msg_lines.append("MODEL: {}".format(model))
                err_msg_lines.append("COUNT: {}".format(count))
                err_msg_lines.append(
                    "SUPPORTED: {}".format(", ".join(supported))
                )
                err_msg = os.linesep.join(err_msg_lines)
                raise DoValidationError(err_msg)
            rtnval = gpu_slug
            return rtnval

        if size_hint is None or len(size_hint) == 0:
            err_msg = "Droplet size hint must not be empty."
            raise DoValidationError(err_msg)

        # Generic / pre-resolved DO size slug is passed through.
        rtnval = size_hint
        return rtnval
