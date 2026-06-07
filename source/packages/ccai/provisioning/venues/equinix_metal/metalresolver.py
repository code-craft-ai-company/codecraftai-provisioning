"""
    .. module:: metalresolver
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: MetalResolver — image / plan / metro resolution for Equinix
               Metal.

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

from ccai.provisioning.venues.equinix_metal.metalerrors import (
    MetalValidationError
)


# Equinix Metro slugs the resolver knows about.
_KNOWN_METROS = frozenset({
    "am", "ch", "da", "dc", "fr", "la", "ld", "ny", "pa", "sg",
    "sl", "sp", "sv", "sy", "ta", "ty",
})


# Catalog of known Metal plans (SKUs).  Bare-metal plans, not VM sizes.
_KNOWN_PLANS = frozenset({
    "c3.small.x86", "c3.medium.x86", "c3.large.x86",
    "m3.small.x86", "m3.large.x86",
    "n3.xlarge.x86",
    "s3.xlarge.x86",
    "g3.large.x86",
})


# GPU device plans keyed by neutral accelerator model.
_ACCELERATOR_PLANS: Dict[str, str] = {
    "A100_SXM": "g3.large.x86",
    "H100_SXM": "g3.large.x86",
    "L40S": "g3.large.x86",
}


# Per-metro plan availability — bare-metal plans are not uniform across
# metros.  An empty set for a metro means "all known plans available".
_METRO_PLAN_AVAILABILITY: Dict[str, frozenset] = {
    "sv": frozenset({"c3.small.x86", "c3.medium.x86", "m3.small.x86",
                      "m3.large.x86", "n3.xlarge.x86", "s3.xlarge.x86",
                      "g3.large.x86"}),
    "da": frozenset({"c3.small.x86", "c3.medium.x86", "c3.large.x86",
                     "m3.small.x86", "m3.large.x86", "n3.xlarge.x86",
                     "s3.xlarge.x86", "g3.large.x86"}),
}


# Neutral size hints mapped to default Metal plans when no accelerator and
# no exact plan slug is supplied.
_SIZE_HINT_PLANS: Dict[str, str] = {
    "small": "c3.small.x86",
    "medium": "c3.medium.x86",
    "large": "c3.large.x86",
    "memory": "m3.large.x86",
    "storage": "s3.xlarge.x86",
    "compute": "n3.xlarge.x86",
}


class MetalResolver:
    """
        Resolves venue-neutral image, size, and metro hints onto Equinix
        Metal OS slugs, plan slugs, and metro slugs.

        Equinix Metal plan availability varies by metro; the resolver
        honours a per-metro plan-availability table.
    """

    def metro_slug(self, *, metro_hint: str) -> str:
        """
            Resolve a neutral region/metro hint to an Equinix metro slug.

            :param metro_hint: Neutral metro/region hint (e.g. ``sv`` or
                               ``us-west``).

            :returns: An Equinix metro slug.
            :raises: MetalValidationError
        """
        if metro_hint is None or len(metro_hint) == 0:
            err_msg = "Equinix Metal metro hint must not be empty."
            raise MetalValidationError(err_msg)

        candidate = metro_hint.strip().lower()
        if candidate in _KNOWN_METROS:
            rtnval = candidate
            return rtnval

        aliases: Dict[str, str] = {
            "us-west": "sv", "us-east": "ny", "us-south": "da",
            "us-central": "ch", "eu-west": "am", "eu-central": "fr",
            "ap-southeast": "sg", "ap-northeast": "ty",
        }
        if candidate in aliases:
            rtnval = aliases[candidate]
            return rtnval

        err_msg_lines = ["Unknown Equinix Metal metro hint."]
        err_msg_lines.append("HINT: {!r}".format(metro_hint))
        err_msg_lines.append("KNOWN: {}".format(
            ", ".join(sorted(_KNOWN_METROS))
        ))
        err_msg = os.linesep.join(err_msg_lines)
        raise MetalValidationError(err_msg)

    def image_to_os_slug(self, *, family: str, version: str,
                         arch: str) -> str:
        """
            Resolve a neutral image triple to an Equinix Metal OS slug.

            ``ubuntu / 24.04 / x86_64`` resolves to ``ubuntu_24_04``.

            :param family: Image family (ubuntu, debian, rhel, ...).
            :param version: Image version string.
            :param arch: Architecture (x86_64 or arm64).

            :returns: An Equinix Metal OS slug.
            :raises: MetalValidationError, SchemaSemanticError
        """
        if family is None or len(family) == 0:
            err_msg = "Equinix Metal image family must not be empty."
            raise MetalValidationError(err_msg)

        if version is None or len(version) == 0:
            err_msg = "Equinix Metal image version must not be empty."
            raise MetalValidationError(err_msg)

        known_families = frozenset({"ubuntu", "debian", "rhel", "rocky",
                                    "almalinux", "fedora"})
        canonical_family = normalize_family(value=family)
        normalized_family = canonical_family.value
        if normalized_family not in known_families:
            err_msg_lines = ["The equinix-metal venue does not support the "
                             "image family."]
            err_msg_lines.append("VENUE: equinix-metal")
            err_msg_lines.append("FAMILY: {}".format(normalized_family))
            err_msg_lines.append("SUPPORTED: {}".format(
                ", ".join(sorted(known_families))
            ))
            err_msg = os.linesep.join(err_msg_lines)
            raise SchemaSemanticError(err_msg)

        normalized_version = version.strip().replace(".", "_")
        rtnval = "{}_{}".format(normalized_family, normalized_version)
        return rtnval

    def size_to_plan(self, *, size_hint: str,
                     accelerators: Optional[List[str]],
                     metro: str) -> str:
        """
            Resolve a neutral size hint (plus optional accelerators) to an
            Equinix Metal plan slug, honouring per-metro availability.

            :param size_hint: Neutral size hint or exact Metal plan slug.
            :param accelerators: Optional list of neutral accelerator model
                                 names.
            :param metro: The resolved metro slug.

            :returns: An Equinix Metal plan slug.
            :raises: MetalValidationError
        """
        size_catalog = CloudInstanceSizeCatalog.default()
        native = size_catalog.resolve(token=size_hint, venue="equinix_metal")
        effective = native if native is not None else size_hint
        size_hint = effective

        resolved_plan: Optional[str] = None

        effective_accelerators = accelerators if accelerators is not None else []
        if len(effective_accelerators) > 0:
            first = effective_accelerators[0]
            if first not in _ACCELERATOR_PLANS:
                err_msg_lines = [
                    "Accelerator model is not on the Equinix Metal catalog."
                ]
                err_msg_lines.append("MODEL: {!r}".format(first))
                err_msg_lines.append("KNOWN: {}".format(
                    ", ".join(sorted(_ACCELERATOR_PLANS.keys()))
                ))
                err_msg = os.linesep.join(err_msg_lines)
                raise MetalValidationError(err_msg)
            resolved_plan = _ACCELERATOR_PLANS[first]

        if resolved_plan is None:
            candidate = size_hint.strip().lower() if size_hint is not None else ""
            if candidate in _KNOWN_PLANS:
                resolved_plan = candidate
            elif candidate in _SIZE_HINT_PLANS:
                resolved_plan = _SIZE_HINT_PLANS[candidate]
            else:
                err_msg_lines = ["Unknown Equinix Metal plan / size hint."]
                err_msg_lines.append("SIZE_HINT: {!r}".format(size_hint))
                err_msg_lines.append("KNOWN_PLANS: {}".format(
                    ", ".join(sorted(_KNOWN_PLANS))
                ))
                err_msg = os.linesep.join(err_msg_lines)
                raise MetalValidationError(err_msg)

        availability = _METRO_PLAN_AVAILABILITY.get(metro, None)
        if availability is not None and resolved_plan not in availability:
            err_msg_lines = [
                "Equinix Metal plan is not available in the requested metro."
            ]
            err_msg_lines.append("PLAN: {}".format(resolved_plan))
            err_msg_lines.append("METRO: {}".format(metro))
            err_msg_lines.append("AVAILABLE: {}".format(
                ", ".join(sorted(availability))
            ))
            err_msg = os.linesep.join(err_msg_lines)
            raise MetalValidationError(err_msg)

        rtnval = resolved_plan
        return rtnval
