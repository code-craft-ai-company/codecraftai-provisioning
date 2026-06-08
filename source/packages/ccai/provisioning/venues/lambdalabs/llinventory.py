"""
    .. module:: llinventory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LlInventory — enumerates run-owned resources for the Lambda
               Labs venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import json
import os

from typing import Any, List

from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.venues.lambdalabs.llnaming import run_id_short
from ccai.provisioning.venues.lambdalabs.llsidecartag import LlSidecarTag


_INVENTORY_FILENAME = "lambdalabs-inventory.json"


class LlInventory:
    """
        Enumerates the Lambda Labs resources owned by a provisioning run.

        Run ownership is decided by the venue-side instance name suffix
        ``-<run-id-short>``; the neutral tag list is recovered from the
        sidecar tag store.
    """

    def __init__(self, *, client: Any,
                 output_root: str = ".output") -> None:
        """
            Construct an LlInventory.

            :param client: The Lambda Labs interop client.
            :param output_root: The output root directory.
        """
        self._client = client
        self._output_root = output_root
        return

    def list_run(self, *, run_id: str, aspects: Any
                 ) -> List[ProvisionedResource]:
        """
            Enumerate every run-owned instance and cluster.

            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.

            :returns: A list of :class:`ProvisionedResource` records.
        """
        suffix = "-" + run_id_short(run_id=run_id)
        sidecar = LlSidecarTag(runid=run_id, output_root=self._output_root)

        out: List[ProvisionedResource] = []

        for instance in self._client.list_instances(aspects=aspects):
            if not instance.name.endswith(suffix):
                continue
            tags = sidecar.read(instance_id=instance.identifier)
            out.append(ProvisionedResource(
                kind="instance", name=instance.name,
                venue_id=instance.identifier,
                attributes={"instance_id": instance.identifier,
                            "instance_type": instance.instance_type_name,
                            "status": instance.status,
                            "ip": instance.ip if instance.ip is not None else ""},
                tags=tags,
            ))

        for cluster in self._client.list_clusters(aspects=aspects):
            if not cluster.name.endswith(suffix):
                continue
            tags = sidecar.read(instance_id=cluster.identifier)
            out.append(ProvisionedResource(
                kind="cluster", name=cluster.name,
                venue_id=cluster.identifier,
                attributes={"cluster_id": cluster.identifier,
                            "instance_type": cluster.instance_type_name,
                            "status": cluster.status,
                            "instance_ids": list(cluster.instance_ids)},
                tags=tags,
            ))

        rtnval = out
        return rtnval

    def persist(self, *, run_id: str,
                resources: List[ProvisionedResource]) -> str:
        """
            Persist an inventory snapshot to the run output directory.

            :param run_id: The provisioning run id.
            :param resources: The resources to persist.

            :returns: The path the inventory snapshot was written to.
        """
        directory = os.path.join(self._output_root, "provisioning", run_id)
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        path = os.path.join(directory, _INVENTORY_FILENAME)
        document = []
        for resource in resources:
            document.append({
                "kind": resource.kind,
                "name": resource.name,
                "venue_id": resource.venue_id,
                "attributes": dict(resource.attributes),
                "tags": dict(resource.tags),
            })

        with open(path, "w", encoding="utf-8") as fh:
            json.dump(document, fh, indent=2, sort_keys=True)

        rtnval = path
        return rtnval
