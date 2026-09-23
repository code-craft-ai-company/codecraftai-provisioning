"""
    .. module:: networkmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: GCP VPC network manager for the Google venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from ccai.provisioning.model.cloud.cloudnetwork import CloudNetwork
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.venues.google.gcpoperations import (
    resource_or_none, wait_for_operation
)
from ccai.provisioning.venues.google.gcpsessionfactory import (
    GcpSessionFactory, SERVICE_COMPUTE
)
from ccai.provisioning.venues.google.gcpidempotency import (
    belongs_to_run
)
from ccai.provisioning.venues.google.gcptagging import (
    from_labels, owner_description, parse_owner_labels,
    RESOURCE_NAME_LABEL_KEY
)


class NetworkManager:
    """
        Manager for GCP VPC networks (``compute.networks``).

        GCP networks are project-scoped global resources.  The venue forces
        custom subnet mode (``auto_create_subnetworks=False``).  Networks have
        no ``labels`` field, so ownership and the neutral resource name are
        carried in the ``description`` field; idempotent ``ensure`` reuses an
        existing owned network.
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
        rtnval = "codecraftai-{}-{}".format(run_id, name).lower()
        return rtnval

    def find(self, *, run_id: str, name: str) -> Optional[Any]:
        """
            Find an existing owned VPC network by run+name.

            :param run_id: Run identifier.
            :param name: Neutral network name.

            :returns: The network resource, or None.
        """
        client = self._client()
        project = self._session_factory.project
        gcp_name = self._gcp_name(run_id=run_id, name=name)
        existing = resource_or_none(fetch=client.get, project=project,
                                    network=gcp_name)
        if existing is None:
            rtnval: Optional[Any] = None
            return rtnval

        labels = parse_owner_labels(description=existing.description)
        if not belongs_to_run(labels=labels, run_id=run_id):
            rtnval = None
            return rtnval

        rtnval = existing
        return rtnval

    def matches(self, *, existing: Any,
                desired: CloudNetwork) -> bool:
        """
            Compare an existing network to the desired CloudNetwork.

            GCP custom-mode networks carry no CIDR, so this compares mode.

            :param existing: GCP network resource.
            :param desired: Desired CloudNetwork.

            :returns: True when no drift is detected.
        """
        rtnval = existing.auto_create_subnetworks is False
        return rtnval

    def ensure(self, *, desired: CloudNetwork, run_id: str,
               default_tags: List[Dict[str, str]],
               aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for a VPC network.

            :param desired: Desired CloudNetwork.
            :param run_id: Run identifier (used for owner marking).
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the network.
        """
        client = self._client()
        project = self._session_factory.project
        gcp_name = self._gcp_name(run_id=run_id, name=desired.name)

        existing = self.find(run_id=run_id, name=desired.name)
        if existing is None:
            description = owner_description(
                run_id=run_id, resource_name=desired.name,
                resource_kind=self.KIND, extra=dict(desired.tags),
                defaults=default_tags,
            )
            body: Dict[str, Any] = {
                "name": gcp_name,
                "auto_create_subnetworks": False,
                "description": description,
            }
            operation = client.insert(project=project,
                                      network_resource=body)
            wait_for_operation(operation=operation)
            existing = client.get(project=project, network=gcp_name)

        labels = parse_owner_labels(description=existing.description)
        if labels is None:
            labels = {}

        network_id = (
            str(existing.id) if existing.id != 0 else gcp_name
        )
        self_link = (
            existing.self_link if len(existing.self_link) > 0
            else "projects/{}/global/networks/{}".format(project, gcp_name)
        )

        attributes: Dict[str, Any] = {}
        attributes["network_id"] = network_id
        attributes["gcp_name"] = gcp_name
        attributes["self_link"] = self_link
        attributes["region"] = desired.region

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=gcp_name,
            attributes=attributes,
            tags=from_labels(labels=labels),
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
            gcp_name = entry.name
            if len(gcp_name) == 0:
                continue
            try:
                client.delete(project=project, network=gcp_name)
                deleted.append(gcp_name)
            except Exception:
                # Best-effort teardown sweep; a resource that fails to delete is left out
                # of the returned list and the sweep continues with the remaining resources.
                pass
        rtnval = deleted
        return rtnval

    def list_raw(self, *, run_id: str) -> List[Any]:
        """
            Return raw owned network resources for the run.

            :param run_id: Run identifier.

            :returns: List of network resources.
        """
        client = self._client()
        project = self._session_factory.project
        out: List[Any] = []
        for entry in client.list(project=project):
            labels = parse_owner_labels(description=entry.description)
            if belongs_to_run(labels=labels, run_id=run_id):
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
            labels = parse_owner_labels(description=entry.description)
            if labels is None:
                labels = {}
            name = labels.get(RESOURCE_NAME_LABEL_KEY, "")
            if len(name) == 0:
                continue
            entry_id = str(entry.id) if entry.id != 0 else entry.name
            attributes: Dict[str, Any] = {}
            attributes["network_id"] = entry_id
            attributes["gcp_name"] = entry.name
            resource = ProvisionedResource(
                kind=self.KIND, name=name,
                venue_id=entry.name,
                attributes=attributes,
                tags=from_labels(labels=labels),
            )
            out.append(resource)
        rtnval = out
        return rtnval
