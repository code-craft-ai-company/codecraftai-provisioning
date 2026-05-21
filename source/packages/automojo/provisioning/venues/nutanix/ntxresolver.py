"""
    .. module:: ntxresolver
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: NtxResolver — resolves neutral image / size / cluster hints
               into Prism Central uuids and hardware descriptors.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Any, Dict, List

from automojo.provisioning.venues.nutanix.nutanixvenueconfig import (
    NutanixVenueConfig
)
from automojo.provisioning.venues.nutanix.ntxerrors import NtxValidationError


class NtxResolver:
    """
        Resolves the neutral resource model's image / size / cluster
        hints onto concrete Prism Central placement targets.

        Image resolution walks the Prism image catalog through the interop
        client; size resolution reads the venue-config size map; cluster
        resolution honours an explicit uuid, falls back to a name hint,
        and finally to the first available cluster.
    """

    def __init__(self, *, client: Any,
                 config: NutanixVenueConfig) -> None:
        """
            Construct an NtxResolver.

            :param client: The Nutanix interop client.
            :param config: The :class:`NutanixVenueConfig`.
        """
        self._client = client
        self._config = config
        return

    def image_to_uuid(self, *, family: str, version: str,
                      arch: str, aspects: Any) -> str:
        """
            Resolve a neutral image triple to a Prism image uuid.

            The neutral ``<family>/<version>`` key is mapped to a Prism
            image name through the venue-config catalog, then verified to
            exist in the Prism image catalog.

            :param family: The CloudImage family.
            :param version: The CloudImage version.
            :param arch: The CloudImage architecture (recorded for
                error context).
            :param aspects: Behaviour control for the interop client.

            :returns: The resolved Prism image uuid.

            :raises: :class:`NtxValidationError` when the image is absent
                from the catalog or the Prism image registry.
        """
        key = self._config.image_key_for(family=family, version=version)
        image_name = self._config.image_catalog.get(key, None)
        if image_name is None:
            err_msg_lines = [
                "Requested image is not present in the Nutanix image "
                "catalog."
            ]
            err_msg_lines.append("LOOKUP-KEY: {}".format(key))
            err_msg_lines.append("ARCHITECTURE: {}".format(arch))
            err_msg_lines.append("KNOWN-KEYS: {}".format(
                ", ".join(sorted(self._config.image_catalog.keys()))
            ))
            err_msg = os.linesep.join(err_msg_lines)
            raise NtxValidationError(err_msg)

        existing = self._client.images.find_by_name(name=image_name,
                                                     aspects=aspects)
        if existing is None:
            err_msg_lines = [
                "Catalog image is not registered in Prism Central."
            ]
            err_msg_lines.append("IMAGE-NAME: {}".format(image_name))
            err_msg_lines.append("LOOKUP-KEY: {}".format(key))
            err_msg = os.linesep.join(err_msg_lines)
            raise NtxValidationError(err_msg)

        rtnval = existing.uuid
        return rtnval

    def size_to_hardware(self, *, size_hint: str) -> Dict[str, int]:
        """
            Resolve a neutral size token to a Prism hardware descriptor.

            :param size_hint: The neutral size token (small, medium, ...).

            :returns: A dict carrying ``num_vcpus``, ``num_cores_per_vcpu``,
                ``memory_mib`` and ``boot_disk_gb``.

            :raises: :class:`NtxValidationError` when the size token is
                absent from the venue-config size map.
        """
        hardware = self._config.size_catalog.get(size_hint, None)
        if hardware is None:
            err_msg_lines = [
                "Requested size token is not present in the Nutanix size "
                "catalog."
            ]
            err_msg_lines.append("SIZE-HINT: {}".format(size_hint))
            err_msg_lines.append("KNOWN-SIZES: {}".format(
                ", ".join(sorted(self._config.size_catalog.keys()))
            ))
            err_msg = os.linesep.join(err_msg_lines)
            raise NtxValidationError(err_msg)

        rtnval = dict(hardware)
        return rtnval

    def pick_cluster(self, *, aspects: Any) -> str:
        """
            Resolve the placement cluster uuid for the run.

            Honours an explicit ``config.cluster_uuid`` first, then a
            ``config.cluster_name`` hint matched against the live Prism
            cluster list, then falls back to the first available cluster.

            :param aspects: Behaviour control for the interop client.

            :returns: The resolved cluster uuid.

            :raises: :class:`NtxValidationError` when no cluster can be
                resolved.
        """
        if (self._config.cluster_uuid is not None
                and len(self._config.cluster_uuid) > 0):
            rtnval = self._config.cluster_uuid
            return rtnval

        available = self._client.clusters.list(aspects=aspects)
        if self._config.cluster_name is not None:
            for cluster in available:
                if cluster.name == self._config.cluster_name:
                    rtnval = cluster.uuid
                    return rtnval

            err_msg_lines = [
                "Configured cluster name was not found in Prism Central."
            ]
            err_msg_lines.append("CLUSTER-NAME: {}".format(
                self._config.cluster_name
            ))
            available_names: List[str] = []
            for cluster in available:
                available_names.append(cluster.name)
            err_msg_lines.append("AVAILABLE: {}".format(
                ", ".join(available_names)
            ))
            err_msg = os.linesep.join(err_msg_lines)
            raise NtxValidationError(err_msg)

        if len(available) > 0:
            first_cluster = available[0]
            rtnval = first_cluster.uuid
            return rtnval

        err_msg_lines = [
            "No cluster could be resolved for VM placement."
        ]
        err_msg_lines.append(
            "Prism Central reported no clusters and no cluster_uuid / "
            "cluster_name was configured."
        )
        err_msg = os.linesep.join(err_msg_lines)
        raise NtxValidationError(err_msg)
