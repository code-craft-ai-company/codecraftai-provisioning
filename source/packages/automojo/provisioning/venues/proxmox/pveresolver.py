"""
    .. module:: pveresolver
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: PveResolver — resolves neutral image / size / storage hints
               onto concrete Proxmox VE primitives.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Any, Dict, Optional

from automojo.provisioning.model.cloud.cloudimage import CloudImage
from automojo.provisioning.venues.proxmox.pveerrors import PveValidationError


# Default neutral-size to hardware mapping.  A spec may carry an
# unrecognised size hint, in which case resolution fails naming the hint.
_DEFAULT_SIZE_TABLE: Dict[str, Dict[str, int]] = {
    "small": {"cores": 2, "memory_mb": 2048, "disk_gb": 20},
    "medium": {"cores": 4, "memory_mb": 8192, "disk_gb": 40},
    "large": {"cores": 8, "memory_mb": 16384, "disk_gb": 80},
    "xlarge": {"cores": 16, "memory_mb": 32768, "disk_gb": 160},
}


class PveImageResolution:
    """
        The outcome of resolving a neutral :class:`CloudImage` onto a
        Proxmox source.  Either a template VMID (``template_vmid``) is set
        or a downloadable cloud-image URL (``image_url``) is set.
    """

    def __init__(self, *, template_vmid: Optional[int] = None,
                 image_url: Optional[str] = None) -> None:
        """
            Construct a PveImageResolution.

            :param template_vmid: The Proxmox template VMID, or ``None``.
            :param image_url: A downloadable cloud-image URL, or ``None``.
        """
        self.template_vmid: Optional[int] = template_vmid
        self.image_url: Optional[str] = image_url
        return


class PveHardware:
    """
        The resolved per-VM hardware shape: CPU cores, memory, and the
        primary disk size in gigabytes.
    """

    def __init__(self, *, cores: int, memory_mb: int, disk_gb: int) -> None:
        """
            Construct a PveHardware.

            :param cores: The number of vCPU cores.
            :param memory_mb: The memory allocation in megabytes.
            :param disk_gb: The primary disk size in gigabytes.
        """
        self.cores: int = cores
        self.memory_mb: int = memory_mb
        self.disk_gb: int = disk_gb
        return


class PveResolver:
    """
        Resolves neutral resource hints onto Proxmox VE primitives.

        The resolver is a pure data transformer — it carries a static
        template catalog (keyed ``family/version/architecture``), a neutral
        size table, and a default storage pool.  It performs no remote I/O.
    """

    def __init__(self, *,
                 template_catalog: Optional[Dict[str, int]] = None,
                 image_url_catalog: Optional[Dict[str, str]] = None,
                 size_table: Optional[Dict[str, Dict[str, int]]] = None,
                 default_storage: str = "local-lvm",
                 default_node: Optional[str] = None) -> None:
        """
            Construct a PveResolver.

            :param template_catalog: Map of ``family/version/arch`` keys to
                Proxmox template VMIDs.
            :param image_url_catalog: Map of ``family/version/arch`` keys to
                downloadable cloud-image URLs.
            :param size_table: Map of neutral size hints to hardware dicts;
                defaults to the packaged table.
            :param default_storage: The default storage pool name.
            :param default_node: Optional default target node name.
        """
        self._template_catalog: Dict[str, int] = (
            dict(template_catalog) if template_catalog is not None else {}
        )
        self._image_url_catalog: Dict[str, str] = (
            dict(image_url_catalog) if image_url_catalog is not None else {}
        )
        if size_table is not None:
            self._size_table: Dict[str, Dict[str, int]] = dict(size_table)
        else:
            self._size_table = dict(_DEFAULT_SIZE_TABLE)
        self._default_storage: str = default_storage
        self._default_node: Optional[str] = default_node
        return

    @property
    def default_storage(self) -> str:
        """
            The default storage pool name.

            :returns: The storage pool name string.
        """
        rtnval = self._default_storage
        return rtnval

    @property
    def default_node(self) -> Optional[str]:
        """
            The default target node name, or ``None``.

            :returns: The node name string or ``None``.
        """
        rtnval = self._default_node
        return rtnval

    @staticmethod
    def _image_key(*, image: CloudImage) -> str:
        """
            Compose the catalog lookup key for a CloudImage.

            :param image: The neutral :class:`CloudImage`.

            :returns: A ``family/version/architecture`` key string.
        """
        rtnval = "{}/{}/{}".format(image.family, image.version,
                                   image.architecture)
        return rtnval

    def image_to_template_or_url(self, *,
                                 image: CloudImage) -> PveImageResolution:
        """
            Resolve a neutral image onto a template VMID or cloud-image URL.

            :param image: The neutral :class:`CloudImage`.

            :returns: A :class:`PveImageResolution`.

            :raises: :class:`PveValidationError` when the image matches
                neither a template VMID nor a downloadable cloud-image URL.
        """
        key = self._image_key(image=image)

        if key in self._template_catalog:
            rtnval = PveImageResolution(
                template_vmid=self._template_catalog[key]
            )
            return rtnval

        if key in self._image_url_catalog:
            rtnval = PveImageResolution(
                image_url=self._image_url_catalog[key]
            )
            return rtnval

        err_msg_lines = ["Proxmox image lookup failed."]
        err_msg_lines.append("LOOKUP KEY: {}".format(key))
        err_msg_lines.append("TEMPLATE CATALOG KEYS: {}".format(
            sorted(self._template_catalog.keys())
        ))
        err_msg_lines.append("IMAGE URL CATALOG KEYS: {}".format(
            sorted(self._image_url_catalog.keys())
        ))
        err_msg = os.linesep.join(err_msg_lines)
        raise PveValidationError(err_msg)

    def size_to_hardware(self, *, size_hint: str) -> PveHardware:
        """
            Resolve a neutral size hint onto a Proxmox hardware shape.

            :param size_hint: The neutral size identifier.

            :returns: A :class:`PveHardware`.

            :raises: :class:`PveValidationError` when the size hint is not
                in the size table.
        """
        if size_hint is None or len(size_hint) == 0:
            raise PveValidationError(
                "Proxmox VM requires a non-empty neutral size hint."
            )

        if size_hint not in self._size_table:
            err_msg_lines = ["Proxmox size resolution failed."]
            err_msg_lines.append("SIZE HINT: {}".format(size_hint))
            err_msg_lines.append("KNOWN SIZES: {}".format(
                sorted(self._size_table.keys())
            ))
            err_msg = os.linesep.join(err_msg_lines)
            raise PveValidationError(err_msg)

        shape = self._size_table[size_hint]
        rtnval = PveHardware(cores=shape["cores"],
                             memory_mb=shape["memory_mb"],
                             disk_gb=shape["disk_gb"])
        return rtnval

    def pick_storage(self, *, required_gb: int,
                     node: Optional[str] = None,
                     content_type: str = "images") -> str:
        """
            Pick a storage pool for a disk of the requested size.

            The resolver carries no live pool inventory, so it returns the
            configured default storage pool; a future revision may inspect
            per-node capacity.

            :param required_gb: The disk size in gigabytes.
            :param node: Optional node name the disk lands on.
            :param content_type: The Proxmox content type required.

            :returns: The storage pool name.
        """
        # `node`, `content_type`, and `required_gb` are retained for
        # interface uniformity; the default-pool policy ignores them.
        _ = (node, content_type, required_gb)
        rtnval = self._default_storage
        return rtnval

    def resolve_node(self, *, instance: Any) -> Optional[str]:
        """
            Resolve the target node for an instance.

            The neutral :class:`CloudInstance` carries no node field, so
            the venue treats the instance ``placement_group`` as the
            target node name when set, otherwise the resolver default.

            :param instance: The neutral :class:`CloudInstance`.

            :returns: The target node name, or ``None`` when unresolvable.
        """
        candidate = getattr(instance, "placement_group", None)
        if candidate is not None and len(candidate) > 0:
            rtnval = candidate
            return rtnval
        rtnval = self._default_node
        return rtnval
