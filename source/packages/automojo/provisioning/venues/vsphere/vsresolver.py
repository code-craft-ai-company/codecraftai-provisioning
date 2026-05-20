"""
    .. module:: vsresolver
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: VsResolver — content-library item / VM-template / datastore
        and instance-size resolution for the VSphere venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Any

from automojo.provisioning.venues.vsphere.vserrors import (
    VsCapacityError, VsValidationError
)
from automojo.provisioning.venues.vsphere.vspherevenueconfig import (
    VSphereVenueConfig
)


# Venue-neutral t-shirt sizes mapped to (vcpu_count, memory_mb, disk_gb).
_SIZE_TABLE = {
    "tiny": (1, 1024, 16),
    "small": (2, 4096, 32),
    "medium": (4, 8192, 64),
    "large": (8, 16384, 128),
    "xlarge": (16, 32768, 256),
}


class LibraryItemRef:
    """
        Reference to a resolved Content Library template item.
    """

    def __init__(self, *, item_id: str, library_id: str, name: str) -> None:
        """
            Construct a LibraryItemRef.

            :param item_id: Content-library item identifier.
            :param library_id: Owning content-library identifier.
            :param name: Item display name.
        """
        self.item_id: str = item_id
        self.library_id: str = library_id
        self.name: str = name
        self.kind: str = "library"
        return


class TemplateRef:
    """
        Reference to a resolved folder-scoped VM template.
    """

    def __init__(self, *, vm_id: str, name: str) -> None:
        """
            Construct a TemplateRef.

            :param vm_id: Template VM identifier.
            :param name: Template VM name.
        """
        self.vm_id: str = vm_id
        self.name: str = name
        self.kind: str = "template"
        return


class HardwareSpec:
    """
        Resolved CPU / RAM / disk hardware sizing for a VM.
    """

    def __init__(self, *, vcpu_count: int, memory_mb: int,
                 disk_gb: int) -> None:
        """
            Construct a HardwareSpec.

            :param vcpu_count: Number of virtual CPUs.
            :param memory_mb: Memory in megabytes.
            :param disk_gb: System disk size in gigabytes.
        """
        self.vcpu_count: int = vcpu_count
        self.memory_mb: int = memory_mb
        self.disk_gb: int = disk_gb
        return


class VsResolver:
    """
        Resolves neutral asks (image, size, datastore) onto vSphere objects.

        Image resolution looks up a Content Library item by tag first, then
        falls back to a folder-scoped VM template; failing both is a
        validate-error.
    """

    def __init__(self, *, ops: Any, config: VSphereVenueConfig) -> None:
        """
            Construct a VsResolver.

            :param ops: A VSphereOps facade.
            :param config: The VSphereVenueConfig.
        """
        self._ops: Any = ops
        self._config: VSphereVenueConfig = config
        return

    def image_to_library_or_template(self, *, family: str, version: str,
                                     architecture: str, aspects: Any) -> Any:
        """
            Resolve a neutral image to a Content Library item or a VM
            template.

            The Content Library is searched first, by a tag matching
            ``family + version``.  When no library item matches, a
            folder-scoped VM template named ``family-version`` is sought.

            :param family: Image family (ubuntu, rhel, windows-server, ...).
            :param version: Image version string.
            :param architecture: Image architecture (informational).
            :param aspects: Behaviour controls.

            :returns: A :class:`LibraryItemRef` or :class:`TemplateRef`.
            :raises: VsValidationError
        """
        item_name = "{}-{}".format(family, version)
        match_tag = "{}-{}".format(family, version)

        library_ids = self._config.content_library_ids
        library_error = None
        if len(library_ids) > 0:
            try:
                item = self._ops.find_library_item(
                    name=item_name, tag=match_tag, library_ids=library_ids,
                    aspects=aspects,
                )
                rtnval = LibraryItemRef(
                    item_id=getattr(item, "item_id", item_name),
                    library_id=getattr(item, "library_id", library_ids[0]),
                    name=getattr(item, "name", item_name),
                )
                return rtnval
            except Exception as xcpt:
                library_error = xcpt

        template_error = None
        try:
            template = self._ops.find_template_vm(
                name=item_name, folder=self._config.template_folder,
                aspects=aspects,
            )
            rtnval = TemplateRef(
                vm_id=getattr(template, "vm", item_name),
                name=getattr(template, "name", item_name),
            )
            return rtnval
        except Exception as xcpt:
            template_error = xcpt

        err_msg_lines = ["VSphere image resolution failed for the request."]
        err_msg_lines.append("FAMILY: {}".format(family))
        err_msg_lines.append("VERSION: {}".format(version))
        err_msg_lines.append("CONTENT-LIBRARY LOOKUP:")
        err_msg_lines.append("    name={}, tag={}".format(item_name,
                                                          match_tag))
        err_msg_lines.append("    result: {}".format(
            "no library configured" if len(library_ids) == 0
            else str(library_error)
        ))
        err_msg_lines.append("TEMPLATE LOOKUP:")
        err_msg_lines.append("    name={}, folder={}".format(
            item_name, self._config.template_folder
        ))
        err_msg_lines.append("    result: {}".format(str(template_error)))
        err_msg = os.linesep.join(err_msg_lines)
        raise VsValidationError(err_msg)

    @staticmethod
    def size_to_hardware(*, size_hint: str) -> HardwareSpec:
        """
            Map a neutral size hint to a :class:`HardwareSpec`.

            :param size_hint: A t-shirt size string (tiny..xlarge).

            :returns: A HardwareSpec.
            :raises: VsValidationError
        """
        normalized = size_hint.lower() if size_hint is not None else ""
        if normalized not in _SIZE_TABLE:
            supported = ", ".join(sorted(_SIZE_TABLE.keys()))
            err_msg_lines = ["Unknown VSphere instance size hint."]
            err_msg_lines.append("REQUESTED: {!r}".format(size_hint))
            err_msg_lines.append("SUPPORTED: {}".format(supported))
            err_msg = os.linesep.join(err_msg_lines)
            raise VsValidationError(err_msg)

        vcpu_count, memory_mb, disk_gb = _SIZE_TABLE[normalized]
        rtnval = HardwareSpec(vcpu_count=vcpu_count, memory_mb=memory_mb,
                              disk_gb=disk_gb)
        return rtnval

    def pick_datastore(self, *, required_gb: float, aspects: Any) -> Any:
        """
            Pick a datastore with at least ``required_gb`` free.

            :param required_gb: Required free space in GB.
            :param aspects: Behaviour controls.

            :returns: A datastore summary object.
            :raises: VsCapacityError
        """
        try:
            datastore = self._ops.find_datastore_with_free_gb(
                min_free_gb=required_gb, aspects=aspects,
            )
        except Exception as xcpt:
            err_msg_lines = ["No datastore can satisfy the size request."]
            err_msg_lines.append("REQUIRED_GB: {}".format(required_gb))
            err_msg_lines.append("CAUSE: {}".format(xcpt))
            err_msg = os.linesep.join(err_msg_lines)
            raise VsCapacityError(err_msg) from None

        rtnval = datastore
        return rtnval
