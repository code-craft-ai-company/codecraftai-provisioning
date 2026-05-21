"""
    .. module:: tpunodemanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: GCP Cloud TPU node manager for the Google venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Optional

from automojo.provisioning.model.cloud.cloudacceleratorcatalog import (
    CloudAcceleratorCatalog
)
from automojo.provisioning.model.cloud.cloudinstance import CloudInstance
from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.venues.google.gcperrors import GcpValidationError
from automojo.provisioning.venues.google.gcpsessionfactory import (
    GcpSessionFactory, SERVICE_TPU
)
from automojo.provisioning.venues.google.gcpidempotency import (
    belongs_to_run
)
from automojo.provisioning.venues.google.gcptagging import (
    base_resource_labels, from_labels, RESOURCE_NAME_LABEL_KEY
)


def is_tpu_instance(*, instance: CloudInstance) -> bool:
    """
        Return True when a CloudInstance's first accelerator is a TPU.

        TPU nodes are a distinct GCP resource type, not a VM accelerator;
        the provisioner branches such instances to the TPU apply path.

        :param instance: The neutral CloudInstance.

        :returns: True when the instance describes a TPU node.
    """
    accelerators = (
        instance.accelerators if instance.accelerators is not None else []
    )
    if len(accelerators) == 0:
        rtnval = False
        return rtnval
    rtnval = accelerators[0].kind == "TPU"
    return rtnval


class TpuNodeManager:
    """
        Manager for GCP Cloud TPU nodes (``tpu_v2.TpuClient``).

        TPU nodes are *not* Compute Engine instances — they are provisioned
        through a separate TPU API surface.  This manager owns the entire TPU
        branch of apply / plan / destroy.
    """

    KIND: str = "tpu"
    VENUE_NAME: str = "gcp"

    def __init__(self, *, session_factory: GcpSessionFactory,
                 catalog: CloudAcceleratorCatalog) -> None:
        """
            Construct a TpuNodeManager.

            :param session_factory: GcpSessionFactory.
            :param catalog: CloudAcceleratorCatalog (for TPU SKU lookup).
        """
        self._session_factory: GcpSessionFactory = session_factory
        self._catalog: CloudAcceleratorCatalog = catalog
        return

    def _client(self) -> Any:
        """
            Return the Cloud TPU client.

            :returns: The TPU client.
        """
        rtnval = self._session_factory.client(service_name=SERVICE_TPU)
        return rtnval

    def _node_id(self, *, run_id: str, name: str) -> str:
        """
            Build the GCP-side TPU node id.

            :param run_id: Run identifier.
            :param name: Neutral instance name.

            :returns: A GCP-conformant TPU node id.
        """
        rtnval = "automojo-{}-{}".format(run_id, name).lower()
        return rtnval

    def _parent(self, *, zone: str) -> str:
        """
            Build the TPU API parent path for a zone.

            :param zone: Zone the TPU node lives in.

            :returns: A ``projects/.../locations/...`` parent path.
        """
        project = self._session_factory.project
        rtnval = "projects/{}/locations/{}".format(project, zone)
        return rtnval

    def resolve_tpu_type(self, *, instance: CloudInstance) -> str:
        """
            Resolve the TPU accelerator type from the catalog.

            :param instance: The neutral CloudInstance describing the TPU.

            :returns: The GCP TPU SKU string.
            :raises: GcpValidationError
        """
        accelerators = (
            instance.accelerators if instance.accelerators is not None else []
        )
        if len(accelerators) == 0 or accelerators[0].kind != "TPU":
            err_msg_lines = ["Instance does not describe a TPU accelerator."]
            err_msg_lines.append("INSTANCE: {}".format(instance.name))
            err_msg = os.linesep.join(err_msg_lines)
            raise GcpValidationError(err_msg)

        first = accelerators[0]
        if first.model is None or len(first.model) == 0:
            err_msg_lines = ["TPU accelerator requires a model (e.g. TPU_V5P)."]
            err_msg_lines.append("INSTANCE: {}".format(instance.name))
            err_msg = os.linesep.join(err_msg_lines)
            raise GcpValidationError(err_msg)

        try:
            sku = self._catalog.resolve(neutral_name=first.model,
                                        venue=self.VENUE_NAME)
        except Exception as xcpt:
            err_msg_lines = ["TPU model could not be resolved by the catalog."]
            err_msg_lines.append("INSTANCE: {}".format(instance.name))
            err_msg_lines.append("MODEL: {}".format(first.model))
            err_msg_lines.append("CAUSE: {}".format(xcpt))
            err_msg = os.linesep.join(err_msg_lines)
            raise GcpValidationError(err_msg) from None

        rtnval = sku
        return rtnval

    def find(self, *, run_id: str, name: str,
             zone: str) -> Optional[Dict[str, Any]]:
        """
            Find an existing owned TPU node by run+name labels.

            :param run_id: Run identifier.
            :param name: Neutral instance name.
            :param zone: Zone the TPU node lives in.

            :returns: The TPU node resource dict, or None.
        """
        client = self._client()
        node_id = self._node_id(run_id=run_id, name=name)
        node_path = "{}/nodes/{}".format(self._parent(zone=zone), node_id)
        existing = client.get_node(name=node_path)
        if existing is None:
            rtnval: Optional[Dict[str, Any]] = None
            return rtnval
        if not belongs_to_run(labels=existing.get("labels", {}),
                              run_id=run_id):
            rtnval = None
            return rtnval
        rtnval = existing
        return rtnval

    def plan_exists(self, *, run_id: str, name: str, zone: str) -> bool:
        """
            Return True when the TPU node already exists for the run.

            :param run_id: Run identifier.
            :param name: Neutral instance name.
            :param zone: Zone the TPU node lives in.

            :returns: True when the TPU node is present.
        """
        rtnval = self.find(run_id=run_id, name=name, zone=zone) is not None
        return rtnval

    def ensure(self, *, desired: CloudInstance, run_id: str, zone: str,
               default_tags: List[Dict[str, str]],
               aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for a TPU node.

            :param desired: Desired CloudInstance describing the TPU.
            :param run_id: Run identifier.
            :param zone: Zone to create the TPU node in.
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the TPU node.
        """
        client = self._client()
        node_id = self._node_id(run_id=run_id, name=desired.name)

        existing = self.find(run_id=run_id, name=desired.name, zone=zone)
        if existing is None:
            tpu_type = self.resolve_tpu_type(instance=desired)
            labels = base_resource_labels(
                run_id=run_id, resource_name=desired.name,
                resource_kind=self.KIND, extra=dict(desired.tags),
                defaults=default_tags,
            )
            node_body: Dict[str, Any] = {
                "accelerator_type": tpu_type,
                "runtime_version": "tpu-vm-base",
                "labels": labels,
            }
            client.create_node(parent=self._parent(zone=zone),
                                node_id=node_id, node=node_body)
            existing = client.get_node(
                name="{}/nodes/{}".format(self._parent(zone=zone), node_id)
            )
            if existing is None:
                existing = node_body

        attributes: Dict[str, Any] = {}
        attributes["tpu_node_id"] = node_id
        attributes["zone"] = zone
        attributes["accelerator_type"] = existing.get("accelerator_type", "")
        attributes["state"] = existing.get("state", "")
        host_ips: List[str] = []
        for endpoint in existing.get("network_endpoints", []):
            ip_addr = endpoint.get("ip_address", "")
            if len(ip_addr) > 0:
                host_ips.append(ip_addr)
        attributes["host_ips"] = host_ips

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=node_id,
            attributes=attributes,
            tags=from_labels(labels=existing.get("labels", {})),
        )
        return rtnval

    def destroy(self, *, run_id: str, zone: str,
                aspects: Any) -> List[str]:
        """
            Destroy every owned TPU node in the zone for the run.

            :param run_id: Run identifier.
            :param zone: Zone to scan.
            :param aspects: Aspects.

            :returns: List of destroyed TPU node ids.
        """
        client = self._client()
        deleted: List[str] = []
        for entry in self.list_raw(run_id=run_id, zone=zone):
            node_name = entry.get("name", "")
            if len(node_name) == 0:
                continue
            try:
                client.delete_node(name=node_name)
                deleted.append(node_name)
            except Exception:
                pass
        rtnval = deleted
        return rtnval

    def list_raw(self, *, run_id: str,
                 zone: str) -> List[Dict[str, Any]]:
        """
            Return raw owned TPU node resource dicts for the run.

            :param run_id: Run identifier.
            :param zone: Zone to scan.

            :returns: List of TPU node resource dicts.
        """
        client = self._client()
        out: List[Dict[str, Any]] = []
        for entry in client.list_nodes(parent=self._parent(zone=zone)):
            if belongs_to_run(labels=entry.get("labels", {}),
                              run_id=run_id):
                out.append(entry)
        rtnval = out
        return rtnval

    def list_owned(self, *, run_id: str,
                   zone: str) -> List[ProvisionedResource]:
        """
            Return all owned TPU nodes for the run as ProvisionedResources.

            :param run_id: Run identifier.
            :param zone: Zone to scan.

            :returns: List of ProvisionedResource entries.
        """
        out: List[ProvisionedResource] = []
        for entry in self.list_raw(run_id=run_id, zone=zone):
            labels = entry.get("labels", {})
            name = labels.get(RESOURCE_NAME_LABEL_KEY, "")
            if len(name) == 0:
                continue
            attributes: Dict[str, Any] = {}
            node_name = entry.get("name", "")
            attributes["tpu_node_id"] = node_name.rsplit("/", 1)[-1]
            attributes["accelerator_type"] = entry.get("accelerator_type", "")
            host_ips: List[str] = []
            for endpoint in entry.get("network_endpoints", []):
                ip_addr = endpoint.get("ip_address", "")
                if len(ip_addr) > 0:
                    host_ips.append(ip_addr)
            attributes["host_ips"] = host_ips
            resource = ProvisionedResource(
                kind=self.KIND, name=name,
                venue_id=attributes["tpu_node_id"],
                attributes=attributes,
                tags=from_labels(labels=labels),
            )
            out.append(resource)
        rtnval = out
        return rtnval
