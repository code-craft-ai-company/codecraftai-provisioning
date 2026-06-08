"""
    .. module:: lvdomainxmlbuilder
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LvDomainXmlBuilder — composes the interop LibvirtDomainSpec
               (and supporting disk / nic specs) for a neutral
               CloudInstance.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Dict, List, Optional

from ccai.provisioning.model.cloud.cloudinstance import CloudInstance
from ccai.provisioning.venues.libvirt.lvmetadatatranslator import (
    LvMetadataTranslator
)

from ccai.interop.libvirt.specs.libvirtdiskspec import LibvirtDiskSpec
from ccai.interop.libvirt.specs.libvirtdomainspec import LibvirtDomainSpec
from ccai.interop.libvirt.specs.libvirtnicspec import LibvirtNicSpec


# Neutral size token -> (vcpus, memory MiB).  libvirt has no native
# instance-type catalog, so the venue maps the neutral size token to a
# vCPU / memory pair directly.
_SIZE_CATALOG: Dict[str, Dict[str, int]] = {
    "small": {"vcpus": 1, "memory_mib": 1024},
    "medium": {"vcpus": 2, "memory_mib": 4096},
    "large": {"vcpus": 4, "memory_mib": 8192},
    "xlarge": {"vcpus": 8, "memory_mib": 16384},
}

_DEFAULT_VCPUS = 2
_DEFAULT_MEMORY_MIB = 4096


class LvDomainXmlBuilder:
    """
        Composes the interop :class:`LibvirtDomainSpec` for a neutral
        :class:`CloudInstance`.

        The neutral ``size`` token is resolved to a ``<vcpu>`` /
        ``<memory>`` pair; the cloned boot volume becomes a virtio disk;
        attached :class:`CloudStorageVolume` volumes become additional
        virtio disks; the cloud-init seed ISO becomes a CD-ROM device;
        and the neutral tag list plus run id is embedded as a
        ``<metadata>`` block via :class:`LvMetadataTranslator`.  The
        result is deterministic for identical inputs.
    """

    def __init__(self, *,
                 metadata_translator: Optional[LvMetadataTranslator] = None
                 ) -> None:
        """
            Construct an LvDomainXmlBuilder.

            :param metadata_translator: Optional
                :class:`LvMetadataTranslator`; defaults to a fresh
                instance.
        """
        if metadata_translator is not None:
            self._metadata_translator: LvMetadataTranslator = (
                metadata_translator
            )
        else:
            self._metadata_translator = LvMetadataTranslator()
        return

    def resolve_size(self, *, size: str) -> Dict[str, int]:
        """
            Resolve a neutral size token to a vCPU / memory pair.

            :param size: The neutral size token.

            :returns: A dict with ``vcpus`` and ``memory_mib`` keys.
        """
        resolved = _SIZE_CATALOG.get(size, None)
        if resolved is not None:
            rtnval = dict(resolved)
            return rtnval

        rtnval = {"vcpus": _DEFAULT_VCPUS, "memory_mib": _DEFAULT_MEMORY_MIB}
        return rtnval

    def build(self, *, instance: CloudInstance, domain_name: str,
              run_id: str, network_name: str, boot_disk_path: str,
              data_disk_paths: List[str],
              seed_iso_path: Optional[str]) -> LibvirtDomainSpec:
        """
            Compose the :class:`LibvirtDomainSpec` for a domain.

            :param instance: The neutral :class:`CloudInstance`.
            :param domain_name: The venue-side domain name.
            :param run_id: The provisioning run id.
            :param network_name: The libvirt network the NIC connects to.
            :param boot_disk_path: The on-host path of the cloned boot
                volume.
            :param data_disk_paths: On-host paths of attached data
                volumes.
            :param seed_iso_path: The on-host path of the cloud-init
                seed ISO, or ``None`` when the domain needs no seed.

            :returns: A :class:`LibvirtDomainSpec`.
        """
        sizing = self.resolve_size(size=instance.size)
        memory_kib = sizing["memory_mib"] * 1024
        vcpus = sizing["vcpus"]

        disks: List[LibvirtDiskSpec] = []
        disks.append(LibvirtDiskSpec(source_path=boot_disk_path,
                                     target_dev="vda",
                                     disk_format="qcow2", bus="virtio",
                                     readonly=False))

        device_index = 0
        for data_path in data_disk_paths:
            target_dev = "vd{}".format(chr(ord("b") + device_index))
            disks.append(LibvirtDiskSpec(source_path=data_path,
                                         target_dev=target_dev,
                                         disk_format="qcow2", bus="virtio",
                                         readonly=False))
            device_index = device_index + 1

        nics: List[LibvirtNicSpec] = []
        nics.append(LibvirtNicSpec(network_name=network_name,
                                   model="virtio"))

        metadata_xml = self._metadata_translator.embed(
            neutral_tags=instance.tags, run_id=run_id
        )

        rtnval = LibvirtDomainSpec(name=domain_name, memory_kib=memory_kib,
                                   vcpus=vcpus, disks=disks, nics=nics,
                                   cdrom_path=seed_iso_path,
                                   metadata_xml=metadata_xml)
        return rtnval
