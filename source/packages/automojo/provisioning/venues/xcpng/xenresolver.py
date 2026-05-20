"""
    .. module:: xenresolver
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: XenResolver — resolves neutral image / size / storage requests
        onto XCP-ng XAPI primitives (Template, vCPU+memory, SR).

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Any, List, Optional

from automojo.provisioning.venues.xcpng.xenerrors import XenValidationError


# Neutral size identifier -> (vcpus, memory_bytes).  XCP-ng has no size
# catalog; the venue maps a small set of neutral size slugs onto explicit
# vCPU / memory pairs.  An unknown slug of the form ``<vcpus>x<gib>`` (for
# example ``4x16``) is parsed directly.
_SIZE_TABLE = {
    "small": (1, 2 * 1024 * 1024 * 1024),
    "medium": (2, 4 * 1024 * 1024 * 1024),
    "large": (4, 8 * 1024 * 1024 * 1024),
    "xlarge": (8, 16 * 1024 * 1024 * 1024),
}

_GIB = 1024 * 1024 * 1024


class XenHardwareShape:
    """
        The resolved hardware shape for a neutral instance size.

        :param vcpus: The number of virtual CPUs.
        :param memory_bytes: The static memory size in bytes.
    """

    def __init__(self, *, vcpus: int, memory_bytes: int) -> None:
        """
            Construct a XenHardwareShape.

            :param vcpus: The number of virtual CPUs.
            :param memory_bytes: The static memory size in bytes.
        """
        self.vcpus: int = vcpus
        self.memory_bytes: int = memory_bytes
        return


class XenResolver:
    """
        Resolves neutral provisioning requests onto XCP-ng XAPI primitives.

        The resolver is a pure mapping component — it owns no transport.  An
        XAPI :class:`XenClient` is handed in per call so the resolver can
        enumerate Templates and SRs to satisfy a request.
    """

    def image_to_template_ref(self, *, client: Any, family: str,
                              version: str, architecture: str,
                              aspects: Any) -> str:
        """
            Resolve a neutral image triple to a XAPI Template uuid.

            The lookup matches a Template whose ``name_label`` contains both
            the family and the version (case-insensitive).  When no Template
            matches, a :class:`XenValidationError` names the lookup so the
            caller can correct the spec or import an XVA.

            :param client: The :class:`XenClient`.
            :param family: The neutral image family (ubuntu, debian, ...).
            :param version: The neutral image version string.
            :param architecture: The neutral image architecture.
            :param aspects: Behaviour control passed to the interop client.

            :returns: The matching Template uuid.

            :raises: XenValidationError
        """
        _ = architecture
        templates = client.Templates.list(aspects=aspects)
        family_lc = family.lower()
        version_lc = version.lower()

        for template in templates:
            label_lc = template.name_label.lower()
            if family_lc in label_lc and version_lc in label_lc:
                rtnval = template.uuid
                return rtnval

        available = [t.name_label for t in templates]
        err_msg_lines = ["XenResolver could not resolve the image to a "
                         "XCP-ng Template."]
        err_msg_lines.append("FAMILY: {}".format(family))
        err_msg_lines.append("VERSION: {}".format(version))
        err_msg_lines.append("LOOKUP: name_label containing both family "
                             "and version (case-insensitive).")
        err_msg_lines.append("AVAILABLE TEMPLATES: {}".format(available))
        err_msg = os.linesep.join(err_msg_lines)
        raise XenValidationError(err_msg)

    def size_to_hardware(self, *, size_hint: str) -> XenHardwareShape:
        """
            Resolve a neutral size slug to a :class:`XenHardwareShape`.

            A slug listed in the venue size table maps to its explicit
            (vcpus, memory) pair.  An unrecognised slug of the form
            ``<vcpus>x<gib>`` (for example ``4x16``) is parsed directly.

            :param size_hint: The neutral size identifier.

            :returns: The resolved :class:`XenHardwareShape`.

            :raises: XenValidationError
        """
        if size_hint is None or len(size_hint) == 0:
            err_msg = "XenResolver.size_to_hardware: size_hint is empty."
            raise XenValidationError(err_msg)

        key = size_hint.lower()
        if key in _SIZE_TABLE:
            vcpus, memory_bytes = _SIZE_TABLE[key]
            rtnval = XenHardwareShape(vcpus=vcpus, memory_bytes=memory_bytes)
            return rtnval

        if "x" in key:
            parts = key.split("x")
            if len(parts) == 2:
                vcpus_text, gib_text = parts
                if vcpus_text.isdigit() and gib_text.isdigit():
                    vcpus = int(vcpus_text)
                    memory_bytes = int(gib_text) * _GIB
                    if vcpus > 0 and memory_bytes > 0:
                        rtnval = XenHardwareShape(
                            vcpus=vcpus, memory_bytes=memory_bytes)
                        return rtnval

        known = sorted(_SIZE_TABLE.keys())
        err_msg_lines = ["XenResolver.size_to_hardware could not resolve a "
                         "size."]
        err_msg_lines.append("SIZE_HINT: {!r}".format(size_hint))
        err_msg_lines.append("KNOWN SLUGS: {}".format(known))
        err_msg_lines.append("OR USE THE <vcpus>x<gib> FORM, e.g. 4x16.")
        err_msg = os.linesep.join(err_msg_lines)
        raise XenValidationError(err_msg)

    def pick_sr(self, *, client: Any, required_gb: int,
                aspects: Any) -> str:
        """
            Pick a storage repository with enough free capacity.

            Shared SRs are preferred over local SRs (a shared SR lets the VM
            migrate within the Pool); among eligible SRs the one with the
            most free space is chosen so a single run does not crowd a small
            SR.

            :param client: The :class:`XenClient`.
            :param required_gb: The required free capacity in gigabytes.
            :param aspects: Behaviour control passed to the interop client.

            :returns: The chosen SR uuid.

            :raises: XenValidationError
        """
        required_bytes = required_gb * _GIB
        srs = client.Sr.list(aspects=aspects)

        eligible: List[Any] = []
        for sr in srs:
            if sr.free >= required_bytes:
                eligible.append(sr)

        if len(eligible) == 0:
            err_msg_lines = ["XenResolver.pick_sr found no SR with enough "
                             "free capacity."]
            err_msg_lines.append("REQUIRED_GB: {}".format(required_gb))
            for sr in srs:
                err_msg_lines.append("    {}: free={} bytes".format(
                    sr.name_label, sr.free))
            err_msg = os.linesep.join(err_msg_lines)
            raise XenValidationError(err_msg)

        def _rank(candidate: Any) -> tuple:
            shared_rank = 0 if candidate.shared is True else 1
            rtnval = (shared_rank, -candidate.free, candidate.name_label)
            return rtnval

        ordered = sorted(eligible, key=_rank)
        chosen = ordered[0]
        rtnval = chosen.uuid
        return rtnval

    def find_sr_for_name(self, *, client: Any, sr_uuid: Optional[str],
                         required_gb: int, aspects: Any) -> str:
        """
            Return an explicit SR uuid when supplied, else pick one.

            :param client: The :class:`XenClient`.
            :param sr_uuid: An explicit SR uuid, or None to auto-pick.
            :param required_gb: The required free capacity in gigabytes.
            :param aspects: Behaviour control passed to the interop client.

            :returns: The SR uuid to use.

            :raises: XenValidationError
        """
        if sr_uuid is not None and len(sr_uuid) > 0:
            rtnval = sr_uuid
            return rtnval
        rtnval = self.pick_sr(client=client, required_gb=required_gb,
                              aspects=aspects)
        return rtnval
