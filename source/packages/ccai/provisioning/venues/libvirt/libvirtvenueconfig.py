"""
    .. module:: libvirtvenueconfig
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LibvirtVenueConfig — venue-level libvirt configuration
               (connection URI, pools, base-image catalog).

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Dict, Optional

from ccai.provisioning.venues.libvirt.lverrors import LvValidationError


# The default neutral-image to base-image-volume map.  The libvirt venue
# clones a Domain's boot disk from one of these base-image volumes via a
# qcow2 backing chain.
_DEFAULT_IMAGE_CATALOG: Dict[str, str] = {
    "ubuntu/24.04": "ubuntu-24.04-server-cloudimg-amd64.img",
    "ubuntu/22.04": "ubuntu-22.04-server-cloudimg-amd64.img",
    "debian/12": "debian-12-genericcloud-amd64.qcow2",
}


class LibvirtVenueConfig:
    """
        Venue-level configuration for the libvirt provisioner.

        Carries the libvirt connection URI, the pool names used for
        base-image volumes / cloned boot disks / cloud-init seed ISOs,
        and the neutral-image to base-image-volume catalog.  The
        provisioner resolves a :class:`CloudImage` to a base-image volume
        through :meth:`base_image_volume_for`.
    """

    def __init__(self, *, connection_uri: str = "qemu:///system",
                 base_image_pool: str = "default",
                 boot_disk_pool: str = "default",
                 cloudinit_pool: str = "default",
                 image_catalog: Optional[Dict[str, str]] = None) -> None:
        """
            Construct a LibvirtVenueConfig.

            :param connection_uri: The libvirt connection URI.
            :param base_image_pool: The pool holding read-only base-image
                volumes used as qcow2 backing files.
            :param boot_disk_pool: The pool into which cloned boot disks
                are written.
            :param cloudinit_pool: The pool into which cloud-init seed
                ISO volumes are uploaded.
            :param image_catalog: Optional override of the neutral-image
                to base-image-volume map.
        """
        self.connection_uri: str = connection_uri
        self.base_image_pool: str = base_image_pool
        self.boot_disk_pool: str = boot_disk_pool
        self.cloudinit_pool: str = cloudinit_pool
        if image_catalog is not None:
            self.image_catalog: Dict[str, str] = dict(image_catalog)
        else:
            self.image_catalog = dict(_DEFAULT_IMAGE_CATALOG)
        return

    def image_key_for(self, *, family: str, version: str) -> str:
        """
            Compose the catalog lookup key for an image family/version.

            :param family: The CloudImage family.
            :param version: The CloudImage version.

            :returns: The ``<family>/<version>`` catalog key.
        """
        rtnval = "{}/{}".format(family, version)
        return rtnval

    def base_image_volume_for(self, *, family: str,
                              version: str) -> str:
        """
            Resolve the base-image volume name for an image.

            :param family: The CloudImage family.
            :param version: The CloudImage version.

            :returns: The base-image volume name within
                ``base_image_pool``.

            :raises: :class:`LvValidationError` when the image is not in
                the catalog.
        """
        key = self.image_key_for(family=family, version=version)
        volume_name = self.image_catalog.get(key, None)
        if volume_name is None:
            err_msg_lines = [
                "Requested image is not present in the libvirt "
                "base-image catalog."
            ]
            err_msg_lines.append("LOOKUP-KEY: {}".format(key))
            err_msg_lines.append("BASE-IMAGE-POOL: {}".format(
                self.base_image_pool
            ))
            err_msg_lines.append("KNOWN-KEYS: {}".format(
                ", ".join(sorted(self.image_catalog.keys()))
            ))
            err_msg = os.linesep.join(err_msg_lines)
            raise LvValidationError(err_msg)

        rtnval = volume_name
        return rtnval
