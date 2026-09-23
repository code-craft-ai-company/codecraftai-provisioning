"""
    .. module:: subnetmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: GCP Subnetwork manager for the Google venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from ccai.provisioning.model.cloud.cloudsubnet import CloudSubnet
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


def _region_of_zone(*, zone: str) -> str:
    """
        Return the region portion of a GCP zone string.

        :param zone: A GCP zone (e.g. ``us-central1-a``).

        :returns: The region (e.g. ``us-central1``).
    """
    if zone.count("-") >= 2:
        rtnval = zone.rsplit("-", 1)[0]
        return rtnval
    rtnval = zone
    return rtnval


class SubnetManager:
    """
        Manager for GCP Subnetworks.

        Subnetworks are region-scoped resources that bind to a parent VPC
        network.  CIDR is realised via ``ip_cidr_range``.  Subnetworks have no
        ``labels`` field, so ownership and the neutral name are carried in the
        ``description`` field.
    """

    KIND: str = "subnet"

    def __init__(self, *, session_factory: GcpSessionFactory) -> None:
        """
            Construct a SubnetManager.

            :param session_factory: GcpSessionFactory.
        """
        self._session_factory: GcpSessionFactory = session_factory
        return

    def _client(self) -> Any:
        """
            Return the compute ``subnetworks`` sub-client.

            :returns: The subnetworks sub-client.
        """
        compute = self._session_factory.client(service_name=SERVICE_COMPUTE)
        rtnval = compute["subnetworks"]
        return rtnval

    def _gcp_name(self, *, run_id: str, name: str) -> str:
        """
            Build the GCP-side subnetwork name.

            :param run_id: Run identifier.
            :param name: Neutral subnet name.

            :returns: A GCP-conformant subnetwork name.
        """
        rtnval = "codecraftai-{}-{}".format(run_id, name).lower()
        return rtnval

    def find(self, *, run_id: str, name: str,
             zone: str) -> Optional[Any]:
        """
            Find an existing owned subnetwork by run+name.

            :param run_id: Run identifier.
            :param name: Neutral subnet name.
            :param zone: Zone of the subnet (region derived from it).

            :returns: The subnetwork resource, or None.
        """
        client = self._client()
        project = self._session_factory.project
        region = _region_of_zone(zone=zone)
        gcp_name = self._gcp_name(run_id=run_id, name=name)
        existing = resource_or_none(fetch=client.get, project=project,
                                    region=region, subnetwork=gcp_name)
        if existing is None:
            rtnval: Optional[Any] = None
            return rtnval

        labels = parse_owner_labels(description=existing.description)
        if not belongs_to_run(labels=labels, run_id=run_id):
            rtnval = None
            return rtnval

        rtnval = existing
        return rtnval

    def ensure(self, *, desired: CloudSubnet, run_id: str,
               network_self_link: str,
               default_tags: List[Dict[str, str]],
               aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for a Subnetwork.

            :param desired: Desired CloudSubnet.
            :param run_id: Run identifier.
            :param network_self_link: Parent VPC network self-link.
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the subnetwork.
        """
        client = self._client()
        project = self._session_factory.project
        region = _region_of_zone(zone=desired.zone)
        gcp_name = self._gcp_name(run_id=run_id, name=desired.name)

        existing = self.find(run_id=run_id, name=desired.name,
                             zone=desired.zone)
        if existing is None:
            description = owner_description(
                run_id=run_id, resource_name=desired.name,
                resource_kind=self.KIND, extra=dict(desired.tags),
                defaults=default_tags,
            )
            body: Dict[str, Any] = {
                "name": gcp_name,
                "network": network_self_link,
                "ip_cidr_range": desired.cidr,
                "region": region,
                "description": description,
            }
            operation = client.insert(project=project, region=region,
                                      subnetwork_resource=body)
            wait_for_operation(operation=operation)
            existing = client.get(project=project, region=region,
                                  subnetwork=gcp_name)

        labels = parse_owner_labels(description=existing.description)
        if labels is None:
            labels = {}

        subnet_id = str(existing.id) if existing.id != 0 else gcp_name
        cidr = (
            existing.ip_cidr_range if len(existing.ip_cidr_range) > 0
            else desired.cidr
        )
        self_link = (
            existing.self_link if len(existing.self_link) > 0
            else "projects/{}/regions/{}/subnetworks/{}".format(
                project, region, gcp_name
            )
        )

        attributes: Dict[str, Any] = {}
        attributes["subnet_id"] = subnet_id
        attributes["gcp_name"] = gcp_name
        attributes["region"] = region
        attributes["cidr"] = cidr
        attributes["self_link"] = self_link

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=gcp_name,
            attributes=attributes,
            tags=from_labels(labels=labels),
        )
        return rtnval

    def destroy(self, *, run_id: str, region: str,
                aspects: Any) -> List[str]:
        """
            Destroy every owned subnetwork in the region for the run.

            :param run_id: Run identifier.
            :param region: GCP region to scan.
            :param aspects: Aspects.

            :returns: List of destroyed subnetwork names.
        """
        client = self._client()
        project = self._session_factory.project
        deleted: List[str] = []
        for entry in self.list_raw(run_id=run_id, region=region):
            gcp_name = entry.name
            if len(gcp_name) == 0:
                continue
            try:
                client.delete(project=project, region=region,
                              subnetwork=gcp_name)
                deleted.append(gcp_name)
            except Exception:
                # Best-effort teardown sweep; a resource that fails to delete is left out
                # of the returned list and the sweep continues with the remaining resources.
                pass
        rtnval = deleted
        return rtnval

    def list_raw(self, *, run_id: str,
                 region: str) -> List[Any]:
        """
            Return raw owned subnetwork resources for the run.

            :param run_id: Run identifier.
            :param region: GCP region to scan.

            :returns: List of subnetwork resources.
        """
        client = self._client()
        project = self._session_factory.project
        out: List[Any] = []
        for entry in client.list(project=project, region=region):
            labels = parse_owner_labels(description=entry.description)
            if belongs_to_run(labels=labels, run_id=run_id):
                out.append(entry)
        rtnval = out
        return rtnval

    def list_owned(self, *, run_id: str,
                   region: str) -> List[ProvisionedResource]:
        """
            Return all owned subnetworks for the run as ProvisionedResources.

            :param run_id: Run identifier.
            :param region: GCP region to scan.

            :returns: List of ProvisionedResource entries.
        """
        out: List[ProvisionedResource] = []
        for entry in self.list_raw(run_id=run_id, region=region):
            labels = parse_owner_labels(description=entry.description)
            if labels is None:
                labels = {}
            name = labels.get(RESOURCE_NAME_LABEL_KEY, "")
            if len(name) == 0:
                continue
            entry_id = str(entry.id) if entry.id != 0 else entry.name
            attributes: Dict[str, Any] = {}
            attributes["subnet_id"] = entry_id
            attributes["gcp_name"] = entry.name
            attributes["cidr"] = entry.ip_cidr_range
            resource = ProvisionedResource(
                kind=self.KIND, name=name,
                venue_id=entry.name,
                attributes=attributes,
                tags=from_labels(labels=labels),
            )
            out.append(resource)
        rtnval = out
        return rtnval
