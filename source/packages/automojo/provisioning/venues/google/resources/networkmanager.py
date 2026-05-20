"""
    .. module:: networkmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: GCP VPC network manager for the Google venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.provisioning.model.cloud.cloudnetwork import CloudNetwork
from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.venues.google.gcpsessionfactory import (
    GcpSessionFactory, SERVICE_COMPUTE
)
from automojo.provisioning.venues.google.gcpidempotency import (
    belongs_to_run
)
from automojo.provisioning.venues.google.gcptagging import (
    base_resource_labels, from_labels, RESOURCE_NAME_LABEL_KEY
)


class NetworkManager:
    """
        Manager for GCP VPC networks (``compute.networks``).

        GCP networks are project-scoped global resources.  The venue forces
        custom subnet mode (``auto_create_subnetworks=False``).  Idempotent
        ``ensure`` is done by label lookup; an existing labelled network is
        reused.
    """

    KIND: str = "network"

    def __init__(self, *, session_factory: GcpSessionFactory) -> None:
        """
            Construct a NetworkManager.

            :param session_factory: GcpSessionFactory.
        """
        self._session_factory: GcpSessionFactory = session_factory
        return

    def _client(self) -> Any:
        """
            Return the compute ``networks`` sub-client.

            :returns: The networks sub-client.
        """
        compute = self._session_factory.client(service_name=SERVICE_COMPUTE)
        rtnval = compute["networks"]
        return rtnval

    def _gcp_name(self, *, run_id: str, name: str) -> str:
        """
            Build the GCP-side network name.

            :param run_id: Run identifier.
            :param name: Neutral network name.

            :returns: A GCP-conformant network name.
        """
        rtnval = "automojo-{}-{}".format(run_id, name).lower()
        return rtnval

    def find(self, *, run_id: str, name: str) -> Optional[Dict[str, Any]]:
        """
            Find an existing owned VPC network by run+name labels.

            :param run_id: Run identifier.
            :param name: Neutral network name.

            :returns: The network resource dict, or None.
        """
        client = self._client()
        project = self._session_factory.project
        gcp_name = self._gcp_name(run_id=run_id, name=name)
        existing = client.get(project=project, network=gcp_name)
        if existing is None:
            rtnval: Optional[Dict[str, Any]] = None
            return rtnval
        if not belongs_to_run(labels=existing.get("labels", {}),
                              run_id=run_id):
            rtnval = None
            return rtnval
        rtnval = existing
        return rtnval

    def matches(self, *, existing: Dict[str, Any],
                desired: CloudNetwork) -> bool:
        """
            Compare an existing network to the desired CloudNetwork.

            GCP custom-mode networks carry no CIDR, so this compares labels.

            :param existing: GCP network resource dict.
            :param desired: Desired CloudNetwork.

            :returns: True when no drift is detected.
        """
        rtnval = existing.get("auto_create_subnetworks", False) is False
        return rtnval

    def ensure(self, *, desired: CloudNetwork, run_id: str,
               default_tags: List[Dict[str, str]],
               aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for a VPC network.

            :param desired: Desired CloudNetwork.
            :param run_id: Run identifier (used for owner labelling).
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the network.
        """
        client = self._client()
        project = self._session_factory.project
        gcp_name = self._gcp_name(run_id=run_id, name=desired.name)

        existing = self.find(run_id=run_id, name=desired.name)
        if existing is None:
            labels = base_resource_labels(
                run_id=run_id, resource_name=desired.name,
                resource_kind=self.KIND, extra=list(desired.tags),
                defaults=default_tags,
            )
            body: Dict[str, Any] = {
                "name": gcp_name,
                "auto_create_subnetworks": False,
                "labels": labels,
            }
            client.insert(project=project, network_resource=body)
            existing = client.get(project=project, network=gcp_name)

        attributes: Dict[str, Any] = {}
        attributes["network_id"] = str(existing.get("id", gcp_name))
        attributes["gcp_name"] = gcp_name
        attributes["self_link"] = existing.get(
            "self_link",
            "projects/{}/global/networks/{}".format(project, gcp_name),
        )
        attributes["region"] = desired.region

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=gcp_name,
            attributes=attributes,
            tags=from_labels(labels=existing.get("labels", {})),
        )
        return rtnval

    def destroy(self, *, run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned VPC network for the run.

            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of destroyed network names.
        """
        client = self._client()
        project = self._session_factory.project
        deleted: List[str] = []
        for entry in self.list_raw(run_id=run_id):
            gcp_name = entry.get("name", "")
            if len(gcp_name) == 0:
                continue
            try:
                client.delete(project=project, network=gcp_name)
                deleted.append(gcp_name)
            except Exception:
                pass
        rtnval = deleted
        return rtnval

    def list_raw(self, *, run_id: str) -> List[Dict[str, Any]]:
        """
            Return raw owned network resource dicts for the run.

            :param run_id: Run identifier.

            :returns: List of network resource dicts.
        """
        client = self._client()
        project = self._session_factory.project
        out: List[Dict[str, Any]] = []
        for entry in client.list(project=project):
            if belongs_to_run(labels=entry.get("labels", {}),
                              run_id=run_id):
                out.append(entry)
        rtnval = out
        return rtnval

    def list_owned(self, *, run_id: str) -> List[ProvisionedResource]:
        """
            Return all owned VPC networks for the run as ProvisionedResources.

            :param run_id: Run identifier.

            :returns: List of ProvisionedResource entries.
        """
        out: List[ProvisionedResource] = []
        for entry in self.list_raw(run_id=run_id):
            labels = entry.get("labels", {})
            name = labels.get(RESOURCE_NAME_LABEL_KEY, "")
            if len(name) == 0:
                continue
            attributes: Dict[str, Any] = {}
            attributes["network_id"] = str(entry.get("id", entry.get("name")))
            attributes["gcp_name"] = entry.get("name", "")
            resource = ProvisionedResource(
                kind=self.KIND, name=name,
                venue_id=entry.get("name", ""),
                attributes=attributes,
                tags=from_labels(labels=labels),
            )
            out.append(resource)
        rtnval = out
        return rtnval
