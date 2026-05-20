"""
    .. module:: placement
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: GCP compact placement ResourcePolicy manager for the Google venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.provisioning.venues.google.gcpsessionfactory import (
    GcpSessionFactory, SERVICE_COMPUTE
)
from automojo.provisioning.venues.google.gcpidempotency import (
    belongs_to_run
)
from automojo.provisioning.venues.google.gcptagging import (
    base_resource_labels
)


class PlacementManager:
    """
        Manager for GCP compact-placement ResourcePolicy objects.

        Unlike AWS EFA (instance-fabric) or InfiniBand, GCP achieves tight
        accelerator coupling for the A3 family via a region-scoped compact
        ``ResourcePolicy``.  One policy is created per logical interconnect
        group; every member instance attaches to it.
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
        rtnval = "automojo-{}-{}".format(run_id, logical_name).lower()
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

        existing = client.get(project=project, region=region,
                              resource_policy=gcp_name)
        if existing is not None and belongs_to_run(
                labels=existing.get("labels", {}), run_id=run_id):
            rtnval = gcp_name
            return rtnval

        labels = base_resource_labels(
            run_id=run_id, resource_name=logical_name,
            resource_kind=self.KIND, defaults=default_tags,
        )
        body: Dict[str, Any] = {
            "name": gcp_name,
            "region": region,
            "group_placement_policy": {
                "collocation": "COLLOCATED",
            },
            "labels": labels,
        }
        client.insert(project=project, region=region,
                      resource_policy_resource=body)
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
            if not belongs_to_run(labels=entry.get("labels", {}),
                                  run_id=run_id):
                continue
            gcp_name = entry.get("name", "")
            if len(gcp_name) == 0:
                continue
            try:
                client.delete(project=project, region=region,
                              resource_policy=gcp_name)
                deleted.append(gcp_name)
            except Exception:
                pass
        rtnval = deleted
        return rtnval
