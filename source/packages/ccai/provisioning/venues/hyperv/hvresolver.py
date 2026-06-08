"""
    .. module:: hvresolver
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: HvResolver — resolves neutral image families and size hints
        onto Hyper-V parent VHD paths and VM hardware shapes.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os
import posixpath

from typing import Dict

from ccai.provisioning.model.cloud.imagefamily import normalize_family
from ccai.provisioning.venues.hyperv.hvhardware import HvHardware
from ccai.provisioning.venues.hyperv.hverrors import HvValidationError


_GIB: int = 1024 * 1024 * 1024
_MIB: int = 1024 * 1024


# Neutral size hint -> (processor_count, memory_startup_bytes, disk_bytes).
_SIZE_TABLE: Dict[str, HvHardware] = {
    "small": HvHardware(processor_count=2,
                        memory_startup_bytes=2 * _GIB,
                        disk_bytes=40 * _GIB),
    "medium": HvHardware(processor_count=4,
                         memory_startup_bytes=8 * _GIB,
                         disk_bytes=80 * _GIB),
    "large": HvHardware(processor_count=8,
                        memory_startup_bytes=16 * _GIB,
                        disk_bytes=160 * _GIB),
    "xlarge": HvHardware(processor_count=16,
                         memory_startup_bytes=32 * _GIB,
                         disk_bytes=320 * _GIB),
}

# Canonical image families known to ship a packaged parent VHDX template.
_KNOWN_FAMILIES = frozenset({
    "ubuntu", "debian", "rhel", "fedora", "amazon-linux", "windows-server"
})

_WINDOWS_FAMILIES = frozenset({"windows-server"})


class HvResolver:
    """
        Resolves neutral resource descriptors onto Hyper-V primitives.

        The resolver owns two mappings: ``image_to_parent_vhd`` turns an
        image family / version / architecture into a parent VHD/VHDX path
        on the host (used for differencing disks), and ``size_to_hardware``
        turns a neutral ``size`` hint into a :class:`HvHardware` shape.
    """

    def __init__(self, *, image_root: str) -> None:
        """
            Construct an HvResolver.

            :param image_root: The host directory holding parent VHD/VHDX
                image templates.
        """
        self._image_root: str = image_root
        return

    def image_to_parent_vhd(self, *, family: str, version: str,
                            arch: str) -> str:
        """
            Resolve a neutral image descriptor onto a parent VHDX path.

            Parent images are expected on the host under ``image_root`` at
            ``<family>-<version>-<arch>.vhdx``.

            :param family: The image family (ubuntu, rhel, windows-server).
            :param version: The image version string.
            :param arch: The image architecture (x86_64, arm64).

            :returns: The host path of the parent VHDX template.

            :raises: HvValidationError when the family is unknown or the
                     hyperv venue cannot serve it.
        """
        canonical_family = normalize_family(value=family)
        family_token = canonical_family.value
        if family_token not in _KNOWN_FAMILIES:
            err_msg_lines = ["The hyperv venue does not support the image "
                             "family."]
            err_msg_lines.append("VENUE: hyperv")
            err_msg_lines.append("SUPPORTED: {}".format(
                ", ".join(sorted(_KNOWN_FAMILIES))))
            err_msg_lines.append("FAMILY: {}".format(family_token))
            err_msg_lines.append("LOOKUP-ROOT: {}".format(self._image_root))
            err_msg = os.linesep.join(err_msg_lines)
            raise HvValidationError(err_msg)

        filename = "{}-{}-{}.vhdx".format(family_token, version, arch)
        rtnval = self._join(root=self._image_root, leaf=filename)
        return rtnval

    def is_windows_family(self, *, family: str) -> bool:
        """
            Report whether an image family is a Windows family.

            :param family: The image family.

            :returns: ``True`` when the family is a Windows family.
        """
        rtnval = family in _WINDOWS_FAMILIES
        return rtnval

    def size_to_hardware(self, *, size_hint: str) -> HvHardware:
        """
            Resolve a neutral size hint onto an :class:`HvHardware` shape.

            :param size_hint: The neutral size identifier.

            :returns: A resolved HvHardware.

            :raises: HvValidationError when the size hint is unknown.
        """
        if size_hint is None or len(size_hint) == 0:
            raise HvValidationError(
                "HvResolver.size_to_hardware requires a non-empty size_hint."
            )

        normalized = size_hint.lower()
        resolved = _SIZE_TABLE.get(normalized, None)
        if resolved is None:
            err_msg_lines = ["Size hint has no Hyper-V hardware mapping."]
            err_msg_lines.append("KNOWN: {}".format(
                ", ".join(sorted(_SIZE_TABLE.keys()))))
            err_msg_lines.append("ACTUAL: {!r}".format(size_hint))
            err_msg = os.linesep.join(err_msg_lines)
            raise HvValidationError(err_msg)

        rtnval = HvHardware(processor_count=resolved.processor_count,
                            memory_startup_bytes=resolved.memory_startup_bytes,
                            disk_bytes=resolved.disk_bytes)
        return rtnval

    @staticmethod
    def _join(*, root: str, leaf: str) -> str:
        """
            Join a host root directory and a leaf name.

            Uses backslash separators when the root looks like a Windows
            path, otherwise POSIX separators (eases test determinism).

            :param root: The root directory.
            :param leaf: The leaf file name.

            :returns: The joined path string.
        """
        if "\\" in root or ":" in root:
            separator = "\\"
            base = root.rstrip("\\")
            rtnval = "{}{}{}".format(base, separator, leaf)
            return rtnval
        rtnval = posixpath.join(root, leaf)
        return rtnval
