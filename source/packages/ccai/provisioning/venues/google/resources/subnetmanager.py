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
from ccai.provisioning.venues.google.gcpsessionfactory import (
    GcpSessionFactory, SERVICE_COMPUTE
)
from ccai.provisioning.venues.google.gcpidempotency import (
    belongs_to_run
)
from ccai.provisioning.venues.google.gcptagging import (
    base_resource_labels, from_labels, RESOURCE_NAME_LABEL_KEY
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
        network.  CIDR is realised via ``ip_cidr_range``.
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
             zone: str) -> Optional[Dict[str, Any]]:
        """
            Find an existing owned subnetwork by run+name labels.

            :param run_id: Run identifier.
            :param name: Neutral subnet name.
            :param zone: Zone of the subnet (region derived from it).

            :returns: The subnetwork resource dict, or None.
        """
        client = self._client()
        project = self._session_factory.project
        region = _region_of_zone(zone=zone)
        gcp_name = self._gcp_name(run_id=run_id, name=name)
        existing = client.get(project=project, region=region,
                              subnetwork=gcp_name)
        if existing is None:
            rtnval: Optional[Dict[str, Any]] = None
            return rtnval
        if not belongs_to_run(labels=existing.get("labels", {}),
                              run_id=run_id):
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
            labels = base_resource_labels(
                run_id=run_id, resource_name=desired.name,
                resource_kind=self.KIND, extra=dict(desired.tags),
                defaults=default_tags,
            )
            body: Dict[str, Any] = {
                "name": gcp_name,
                "network": network_self_link,
                "ip_cidr_range": desired.cidr,
                "region": region,
                "labels": labels,
            }
            client.insert(project=project, region=region,
                          subnetwork_resource=body)
            existing = client.get(project=project, region=region,
                                  subnetwork=gcp_name)

        attributes: Dict[str, Any] = {}
        attributes["subnet_id"] = str(existing.get("id", gcp_name))
        attributes["gcp_name"] = gcp_name
        attributes["region"] = region
        attributes["cidr"] = existing.get("ip_cidr_range", desired.cidr)
        attributes["self_link"] = existing.get(
            "self_link",
            "projects/{}/regions/{}/subnetworks/{}".format(
                project, region, gcp_name
            ),
        )

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=gcp_name,
            attributes=attributes,
            tags=from_labels(labels=existing.get("labels", {})),
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
            gcp_name = entry.get("name", "")
            if len(gcp_name) == 0:
                continue
            try:
                client.delete(project=project, region=region,
                              subnetwork=gcp_name)
                deleted.append(gcp_name)
            except Exception:
                pass
        rtnval = deleted
        return rtnval

    def list_raw(self, *, run_id: str,
                 region: str) -> List[Dict[str, Any]]:
        """
            Return raw owned subnetwork resource dicts for the run.

            :param run_id: Run identifier.
            :param region: GCP region to scan.

            :returns: List of subnetwork resource dicts.
        """
        client = self._client()
        project = self._session_factory.project
        out: List[Dict[str, Any]] = []
        for entry in client.list(project=project, region=region):
            if belongs_to_run(labels=entry.get("labels", {}),
                              run_id=run_id):
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
            labels = entry.get("labels", {})
            name = labels.get(RESOURCE_NAME_LABEL_KEY, "")
            if len(name) == 0:
                continue
            attributes: Dict[str, Any] = {}
            attributes["subnet_id"] = str(entry.get("id", entry.get("name")))
            attributes["gcp_name"] = entry.get("name", "")
            attributes["cidr"] = entry.get("ip_cidr_range", "")
            resource = ProvisionedResource(
                kind=self.KIND, name=name,
                venue_id=entry.get("name", ""),
                attributes=attributes,
                tags=from_labels(labels=labels),
            )
            out.append(resource)
        rtnval = out
        return rtnval
