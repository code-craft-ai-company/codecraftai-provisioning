"""
    .. module:: imagefamily
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Canonical neutral image vocabulary — family + architecture
        tokens, version-format validation, and string coercion helpers.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os
import re

from enum import Enum
from typing import Dict, Union

from ccai.provisioning.model.exceptions import SchemaSemanticError


class ImageFamily(str, Enum):
    """
        Canonical, venue-neutral image family tokens.

        Every venue resolver agrees on this set.  A venue that genuinely
        cannot serve a member rejects it explicitly rather than failing in
        a venue-specific way.  The string value of each member is the
        canonical token stored on a :class:`CloudImage`.
    """
    UBUNTU = "ubuntu"
    DEBIAN = "debian"
    RHEL = "rhel"
    ROCKY = "rocky"
    ALMALINUX = "almalinux"
    FEDORA = "fedora"
    WINDOWS_SERVER = "windows-server"
    AMAZON_LINUX = "amazon-linux"


class ImageArchitecture(str, Enum):
    """
        Canonical, venue-neutral CPU architecture tokens for an image.
    """
    X86_64 = "x86_64"
    ARM64 = "arm64"


# Common aliases that coerce onto a canonical ImageFamily.
_FAMILY_ALIASES: Dict[str, ImageFamily] = {
    "ubuntu": ImageFamily.UBUNTU,
    "debian": ImageFamily.DEBIAN,
    "rhel": ImageFamily.RHEL,
    "redhat": ImageFamily.RHEL,
    "red-hat": ImageFamily.RHEL,
    "rocky": ImageFamily.ROCKY,
    "rockylinux": ImageFamily.ROCKY,
    "rocky-linux": ImageFamily.ROCKY,
    "almalinux": ImageFamily.ALMALINUX,
    "alma": ImageFamily.ALMALINUX,
    "alma-linux": ImageFamily.ALMALINUX,
    "fedora": ImageFamily.FEDORA,
    "windows": ImageFamily.WINDOWS_SERVER,
    "windows-server": ImageFamily.WINDOWS_SERVER,
    "windowsserver": ImageFamily.WINDOWS_SERVER,
    "windows_server": ImageFamily.WINDOWS_SERVER,
    "amazon-linux": ImageFamily.AMAZON_LINUX,
    "amazonlinux": ImageFamily.AMAZON_LINUX,
    "amazon_linux": ImageFamily.AMAZON_LINUX,
    "amzn": ImageFamily.AMAZON_LINUX,
}


# Common aliases that coerce onto a canonical ImageArchitecture.
_ARCHITECTURE_ALIASES: Dict[str, ImageArchitecture] = {
    "x86_64": ImageArchitecture.X86_64,
    "amd64": ImageArchitecture.X86_64,
    "x64": ImageArchitecture.X86_64,
    "arm64": ImageArchitecture.ARM64,
    "aarch64": ImageArchitecture.ARM64,
}


# A version is one or more dotted numeric components (``24.04``, ``9.4``,
# ``12``).  No leading / trailing dot, no empty components.
_VERSION_PATTERN = re.compile(r"^[0-9]+(\.[0-9]+)*$")


def validate_version(*, version: str) -> None:
    """
        Validate that an image version is a dotted numeric string.

        Accepts ``"24.04"``, ``"12"``, ``"9.4"``; rejects empty strings,
        codenames, and malformed dotted values.

        :param version: The image version string to validate.

        :raises: SchemaSemanticError when the version is malformed.
    """
    if version is None or len(version) == 0:
        raise SchemaSemanticError("Image version must not be empty.")

    matched = _VERSION_PATTERN.match(version)
    if matched is None:
        err_msg_lines = ["Image version is not a dotted numeric string."]
        err_msg_lines.append("VERSION: {!r}".format(version))
        err_msg_lines.append("EXPECTED: digits separated by single dots, "
                             "e.g. 24.04, 12, 9.4")
        err_msg = os.linesep.join(err_msg_lines)
        raise SchemaSemanticError(err_msg)

    return


def normalize_family(*, value: Union[ImageFamily, str]) -> ImageFamily:
    """
        Coerce a family value onto a canonical :class:`ImageFamily` member.

        Accepts an :class:`ImageFamily` directly, the canonical token, or a
        common alias (e.g. ``amazonlinux`` -> ``AMAZON_LINUX``).

        :param value: An ImageFamily member or a family string.

        :returns: The canonical ImageFamily member.

        :raises: SchemaSemanticError when the value is not a known family.
    """
    if isinstance(value, ImageFamily):
        rtnval = value
        return rtnval

    if value is None or len(value) == 0:
        raise SchemaSemanticError("Image family must not be empty.")

    lookup_key = value.strip().lower()
    resolved = _FAMILY_ALIASES.get(lookup_key, None)
    if resolved is None:
        valid_tokens = sorted(member.value for member in ImageFamily)
        err_msg_lines = ["Image family is not a canonical image family."]
        err_msg_lines.append("FAMILY: {!r}".format(value))
        err_msg_lines.append("VALID: {}".format(", ".join(valid_tokens)))
        err_msg = os.linesep.join(err_msg_lines)
        raise SchemaSemanticError(err_msg)

    rtnval = resolved
    return rtnval


def normalize_architecture(
        *, value: Union[ImageArchitecture, str]) -> ImageArchitecture:
    """
        Coerce an architecture value onto a canonical
        :class:`ImageArchitecture` member.

        Accepts an :class:`ImageArchitecture` directly, the canonical token,
        or a common alias (``amd64`` -> ``X86_64``, ``aarch64`` -> ``ARM64``).

        :param value: An ImageArchitecture member or an architecture string.

        :returns: The canonical ImageArchitecture member.

        :raises: SchemaSemanticError when the value is not a known
                 architecture.
    """
    if isinstance(value, ImageArchitecture):
        rtnval = value
        return rtnval

    if value is None or len(value) == 0:
        raise SchemaSemanticError("Image architecture must not be empty.")

    lookup_key = value.strip().lower()
    resolved = _ARCHITECTURE_ALIASES.get(lookup_key, None)
    if resolved is None:
        valid_tokens = sorted(member.value for member in ImageArchitecture)
        err_msg_lines = ["Image architecture is not a canonical "
                         "architecture."]
        err_msg_lines.append("ARCHITECTURE: {!r}".format(value))
        err_msg_lines.append("VALID: {}".format(", ".join(valid_tokens)))
        err_msg = os.linesep.join(err_msg_lines)
        raise SchemaSemanticError(err_msg)

    rtnval = resolved
    return rtnval
