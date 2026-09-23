"""
    .. module:: placement
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: GCP compact placement ResourcePolicy manager for the Google venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List

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
    owner_description, parse_owner_labels
)


class PlacementManager:
    """
        Manager for GCP compact-placement ResourcePolicy objects.

        Unlike AWS EFA (instance-fabric) or InfiniBand, GCP achieves tight
        accelerator coupling for the A3 family via a region-scoped compact
        ``ResourcePolicy``.  One policy is created per logical interconnect
        group; every member instance attaches to it.  ResourcePolicy has no
        ``labels`` field, so ownership is carried in the ``description`` field.
    """

    KIND: str = "placement"

    def __init__(self, *, session_factory: GcpSessionFactory) -> None:
        """
            Construct a PlacementManager.

            :param session_factory: GcpSessionFactory.
        """
        self._session_factory: GcpSessionFactory = session_factory
        return

    def _client(self) -> Any:
        """
            Return the compute ``resource_policies`` sub-client.

            :returns: The resource_policies sub-client.
        """
        compute = self._session_factory.client(service_name=SERVICE_COMPUTE)
        rtnval = compute["resource_policies"]
        return rtnval

    def policy_name(self, *, run_id: str, logical_name: str) -> str:
        """
            Build the GCP-side ResourcePolicy name.

            :param run_id: Run identifier.
            :param logical_name: Logical interconnect group name.

            :returns: A GCP-conformant resource-policy name.
        """
        rtnval = "codecraftai-{}-{}".format(run_id, logical_name).lower()
        return rtnval

    def ensure(self, *, run_id: str, logical_name: str, region: str,
               default_tags: List[Dict[str, str]],
               aspects: Any) -> str:
        """
            Match-then-act create-or-reuse for a compact ResourcePolicy.

            :param run_id: Run identifier.
            :param logical_name: Logical interconnect group name.
            :param region: GCP region the policy lives in.
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: The ResourcePolicy name.
        """
        client = self._client()
        project = self._session_factory.project
        gcp_name = self.policy_name(run_id=run_id,
                                    logical_name=logical_name)

        existing = resource_or_none(fetch=client.get, project=project,
                                    region=region, resource_policy=gcp_name)
        if existing is not None:
            existing_labels = parse_owner_labels(
                description=existing.description
            )
            if belongs_to_run(labels=existing_labels, run_id=run_id):
                rtnval = gcp_name
                return rtnval

        description = owner_description(
            run_id=run_id, resource_name=logical_name,
            resource_kind=self.KIND, defaults=default_tags,
        )
        body: Dict[str, Any] = {
            "name": gcp_name,
            "region": region,
            "group_placement_policy": {
                "collocation": "COLLOCATED",
            },
            "description": description,
        }
        operation = client.insert(project=project, region=region,
                                  resource_policy_resource=body)
        wait_for_operation(operation=operation)
        rtnval = gcp_name
        return rtnval

    def destroy(self, *, run_id: str, region: str,
                aspects: Any) -> List[str]:
        """
            Destroy every owned ResourcePolicy in the region for the run.

            :param run_id: Run identifier.
            :param region: GCP region to scan.
            :param aspects: Aspects.

            :returns: List of destroyed resource-policy names.
        """
        client = self._client()
        project = self._session_factory.project
        deleted: List[str] = []
        for entry in client.list(project=project, region=region):
            labels = parse_owner_labels(description=entry.description)
            if not belongs_to_run(labels=labels, run_id=run_id):
                continue
            gcp_name = entry.name
            if len(gcp_name) == 0:
                continue
            try:
                client.delete(project=project, region=region,
                              resource_policy=gcp_name)
                deleted.append(gcp_name)
            except Exception:
                # Best-effort teardown sweep; a resource that fails to delete is left out
                # of the returned list and the sweep continues with the remaining resources.
                pass
        rtnval = deleted
        return rtnval
