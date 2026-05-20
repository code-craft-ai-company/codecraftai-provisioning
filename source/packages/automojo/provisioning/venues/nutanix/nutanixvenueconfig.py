"""
    .. module:: nutanixvenueconfig
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: NutanixVenueConfig — venue-level Prism Central configuration
               (cluster placement target, image catalog, size map, Objects
               availability).

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Dict, Optional


# Default neutral-size to Prism vCPU/RAM/disk hardware map.  The Nutanix
# venue resolves a :class:`CloudInstance` ``size`` token through this map.
_DEFAULT_SIZE_CATALOG: Dict[str, Dict[str, int]] = {
    "small": {"num_vcpus": 1, "num_cores_per_vcpu": 1,
              "memory_mib": 2048, "boot_disk_gb": 20},
    "medium": {"num_vcpus": 2, "num_cores_per_vcpu": 1,
               "memory_mib": 4096, "boot_disk_gb": 40},
    "large": {"num_vcpus": 4, "num_cores_per_vcpu": 1,
              "memory_mib": 8192, "boot_disk_gb": 80},
    "xlarge": {"num_vcpus": 8, "num_cores_per_vcpu": 1,
               "memory_mib": 16384, "boot_disk_gb": 160},
}

# Default neutral-image to Prism image-name map.  The Nutanix venue
# verifies a :class:`CloudImage` resolves to a registered Prism image.
_DEFAULT_IMAGE_CATALOG: Dict[str, str] = {
    "ubuntu/24.04": "ubuntu-24.04-server-cloudimg-amd64",
    "ubuntu/22.04": "ubuntu-22.04-server-cloudimg-amd64",
    "debian/12": "debian-12-genericcloud-amd64",
}


class NutanixVenueConfig:
    """
        Venue-level configuration for the Nutanix provisioner.

        Carries the placement cluster (uuid or name hint), the optional
        storage-container uuid for additional disks, the neutral-image to
        Prism-image-name catalog, the neutral-size to Prism-hardware map,
        and the flag declaring whether Nutanix Objects is configured in
        the spec's ``apod`` (without which :class:`CloudObjectBucket`
        requests are validate-errors).
    """

    def __init__(self, *, cluster_uuid: Optional[str] = None,
                 cluster_name: Optional[str] = None,
                 storage_container_uuid: Optional[str] = None,
                 objects_configured: bool = False,
                 image_catalog: Optional[Dict[str, str]] = None,
                 size_catalog: Optional[Dict[str, Dict[str, int]]] = None
                 ) -> None:
        """
            Construct a NutanixVenueConfig.

            :param cluster_uuid: The placement cluster uuid; when ``None``
                the resolver picks the first available cluster.
            :param cluster_name: Optional cluster-name placement hint used
                when no uuid is supplied.
            :param storage_container_uuid: Optional storage-container uuid
                for additional :class:`CloudStorageVolume` volume groups.
            :param objects_configured: ``True`` when Nutanix Objects is
                configured for the run; gates :class:`CloudObjectBucket`.
            :param image_catalog: Optional override of the neutral-image
                to Prism-image-name map.
            :param size_catalog: Optional override of the neutral-size to
                Prism-hardware map.
        """
        self.cluster_uuid: Optional[str] = cluster_uuid
        self.cluster_name: Optional[str] = cluster_name
        self.storage_container_uuid: Optional[str] = storage_container_uuid
        self.objects_configured: bool = objects_configured
        if image_catalog is not None:
            self.image_catalog: Dict[str, str] = dict(image_catalog)
        else:
            self.image_catalog = dict(_DEFAULT_IMAGE_CATALOG)
        if size_catalog is not None:
            self.size_catalog: Dict[str, Dict[str, int]] = {
                key: dict(value) for key, value in size_catalog.items()
            }
        else:
            self.size_catalog = {
                key: dict(value)
                for key, value in _DEFAULT_SIZE_CATALOG.items()
            }
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
