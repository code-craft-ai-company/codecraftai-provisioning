"""
    .. module:: hvhostconfig
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: HvHostConfig — per-run Hyper-V host configuration carrier.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Optional


class HvHostConfig:
    """
        Per-run Hyper-V host configuration.

        Hyper-V has no project / region surface; instead a run targets a
        single host (or Failover Cluster) and a set of host filesystem
        paths used for VM configuration, VHDX storage, parent-VHD images
        and config-drive ISOs.
    """

    def __init__(self, *, host: str,
                 vm_root: str = "C:\\ccai\\vms",
                 vhd_root: str = "C:\\ccai\\vhds",
                 image_root: str = "C:\\ccai\\images",
                 iso_root: str = "C:\\ccai\\isos",
                 external_adapter_name: Optional[str] = None) -> None:
        """
            Construct an HvHostConfig.

            :param host: The Hyper-V host name or Failover Cluster name.
            :param vm_root: Host directory for VM configuration files.
            :param vhd_root: Host directory for created VHDX disks.
            :param image_root: Host directory holding parent VHD/VHDX
                images keyed by family/version.
            :param iso_root: Host directory for config-drive ISO files.
            :param external_adapter_name: Physical adapter name bound to an
                External VMSwitch; required when a network maps to an
                External switch.
        """
        self.host: str = host
        self.vm_root: str = vm_root
        self.vhd_root: str = vhd_root
        self.image_root: str = image_root
        self.iso_root: str = iso_root
        self.external_adapter_name: Optional[str] = external_adapter_name
        return
