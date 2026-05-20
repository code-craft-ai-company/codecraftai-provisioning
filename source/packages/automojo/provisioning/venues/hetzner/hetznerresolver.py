"""
    .. module:: hetznerresolver
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Resolvers from neutral CloudImage / size hints to Hetzner slugs.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import List, Optional

from automojo.provisioning.venues.hetzner.hetznererrors import (
    HetznerValidationError
)


# Image families Hetzner publishes as Cloud images.  Maps the neutral
# family to the Hetzner image-name prefix.
_IMAGE_FAMILY_PREFIX = {
    "ubuntu": "ubuntu",
    "debian": "debian",
    "fedora": "fedora",
    "rhel": "rocky",  # Hetzner ships Rocky as the RHEL-class image.
    "centos": "centos",
}

# Server-type catalog Hetzner publishes.  Shared CPU (cx/cpx), dedicated
# (ccx), Arm (cax), and the small GPU set.
_KNOWN_SERVER_TYPES = frozenset({
    "cx22", "cx32", "cx42", "cx52",
    "cpx11", "cpx21", "cpx31", "cpx41", "cpx51",
    "ccx13", "ccx23", "ccx33", "ccx43", "ccx53", "ccx63",
    "cax11", "cax21", "cax31", "cax41",
})

# Minimal GPU catalog — only what Hetzner publishes.
_GPU_MODEL_TO_TYPE = {
    "rtx-4000-sff": "gpu-rtx4000",
    "rtx4000": "gpu-rtx4000",
}

# Default size hint when none resolves cleanly.
_DEFAULT_SERVER_TYPE = "cx22"


class HetznerResolver:
    """
        Resolver translating the neutral image triple and size hints into
        Hetzner image names and server-type slugs.

        The resolver only knows the small catalog Hetzner publishes; an
        unknown family or accelerator is a hard failure.
    """

    @classmethod
    def image_to_name(cls, *, family: str, version: str,
                      arch: str) -> str:
        """
            Resolve a Hetzner image name from the neutral image triple.

            ``ubuntu / 24.04`` resolves to ``ubuntu-24.04``.

            :param family: Neutral image family (ubuntu, debian, ...).
            :param version: Image version string.
            :param arch: Architecture (x86_64 or arm64).

            :returns: The Hetzner image name slug.
            :raises: HetznerValidationError
        """
        normalized_family = family.lower()
        if normalized_family not in _IMAGE_FAMILY_PREFIX:
            known = ", ".join(sorted(_IMAGE_FAMILY_PREFIX.keys()))
            err_msg_lines = ["Image family is unknown to the Hetzner resolver."]
            err_msg_lines.append("KNOWN: {}".format(known))
            err_msg_lines.append("ACTUAL: {!r}".format(family))
            err_msg = os.linesep.join(err_msg_lines)
            raise HetznerValidationError(err_msg)

        if version is None or len(version) == 0:
            raise HetznerValidationError(
                "Image version must not be empty for Hetzner resolution."
            )

        prefix = _IMAGE_FAMILY_PREFIX[normalized_family]
        rtnval = "{}-{}".format(prefix, version)
        return rtnval

    @classmethod
    def size_to_type(cls, *, size_hint: str,
                     accelerators: Optional[List[str]] = None) -> str:
        """
            Resolve a Hetzner server-type slug from a size hint.

            When accelerators are requested the GPU catalog takes priority;
            otherwise the size hint must name a known server type.

            :param size_hint: Neutral size identifier (e.g. ``cx22``).
            :param accelerators: Optional list of accelerator model names.

            :returns: The Hetzner server-type slug.
            :raises: HetznerValidationError
        """
        effective_accelerators = accelerators if accelerators is not None else []

        if len(effective_accelerators) > 0:
            first_model = effective_accelerators[0].lower()
            if first_model not in _GPU_MODEL_TO_TYPE:
                known = ", ".join(sorted(set(_GPU_MODEL_TO_TYPE.keys())))
                err_msg_lines = [
                    "Accelerator model is unknown to the Hetzner resolver."
                ]
                err_msg_lines.append("KNOWN: {}".format(known))
                err_msg_lines.append("ACTUAL: {!r}".format(
                    effective_accelerators[0]))
                err_msg = os.linesep.join(err_msg_lines)
                raise HetznerValidationError(err_msg)
            rtnval = _GPU_MODEL_TO_TYPE[first_model]
            return rtnval

        if size_hint is None or len(size_hint) == 0:
            rtnval = _DEFAULT_SERVER_TYPE
            return rtnval

        normalized_hint = size_hint.lower()
        if normalized_hint not in _KNOWN_SERVER_TYPES:
            known = ", ".join(sorted(_KNOWN_SERVER_TYPES))
            err_msg_lines = [
                "Server type is unknown to the Hetzner resolver."
            ]
            err_msg_lines.append("KNOWN: {}".format(known))
            err_msg_lines.append("ACTUAL: {!r}".format(size_hint))
            err_msg = os.linesep.join(err_msg_lines)
            raise HetznerValidationError(err_msg)

        rtnval = normalized_hint
        return rtnval

    @classmethod
    def known_server_types(cls) -> List[str]:
        """
            Return the sorted list of known Hetzner server types.

            :returns: A sorted list of server-type slugs.
        """
        rtnval = sorted(_KNOWN_SERVER_TYPES)
        return rtnval
