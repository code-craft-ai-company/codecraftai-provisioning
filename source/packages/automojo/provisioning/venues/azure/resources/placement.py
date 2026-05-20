"""
    .. module:: placement
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Azure Proximity Placement Group manager for InfiniBand SKUs.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List

from automojo.provisioning.venues.azure.azureidempotency import (
    belongs_to_run, get_or_none
)
from automojo.provisioning.venues.azure.azuresessionfactory import (
    AzureSessionFactory
)
from automojo.provisioning.venues.azure.azuretagging import azure_tags_for


class PlacementManager:
    """
        Manager for Azure Proximity Placement Groups (PPGs).

        InfiniBand-capable SKUs (NDv5 / NCv4) require all VMs in an
        interconnect group to share a Proximity Placement Group so RDMA
        traffic stays within a single low-latency datacentre zone.  ``ensure``
        is idempotent; the PPG is named from a logical interconnect-group
        label.
    """

    KIND: str = "placement_group"

    def __init__(self, *, session_factory: AzureSessionFactory) -> None:
        """
            Construct a PlacementManager.

            :param session_factory: AzureSessionFactory.
        """
        self._session_factory: AzureSessionFactory = session_factory
        return

    def _compute(self) -> Any:
        """
            Return the ComputeManagementClient.

            :returns: A ComputeManagementClient.
        """
        rtnval = self._session_factory.compute_client()
        return rtnval

    def ppg_name(self, *, logical_name: str) -> str:
        """
            Build the Proximity Placement Group name.

            :param logical_name: Logical interconnect-group label.

            :returns: The PPG name.
        """
        rtnval = "{}-ppg".format(logical_name)
        return rtnval

    def ensure(self, *, logical_name: str, resource_group: str,
               location: str, run_id: str,
               default_tags: List[Dict[str, str]],
               aspects: Any) -> str:
        """
            Create or reuse a Proximity Placement Group.

            :param logical_name: Logical interconnect-group label.
            :param resource_group: ResourceGroup name.
            :param location: Azure location.
            :param run_id: Run identifier (used for owner tagging).
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: The Proximity Placement Group resource id.
        """
        client = self._compute()
        ppg_name = self.ppg_name(logical_name=logical_name)
        existing = get_or_none(
            getter=client.proximity_placement_groups.get,
            resource_group_name=resource_group,
            proximity_placement_group_name=ppg_name,
        )

        if existing is None:
            tags = azure_tags_for(run_id=run_id, resource_name=ppg_name,
                                  resource_kind=self.KIND,
                                  defaults=default_tags)
            params: Dict[str, Any] = {
                "location": location,
                "proximity_placement_group_type": "Standard",
                "tags": tags,
            }
            existing = client.proximity_placement_groups.create_or_update(
                resource_group_name=resource_group,
                proximity_placement_group_name=ppg_name,
                parameters=params,
            )

        rtnval = getattr(existing, "id", ppg_name)
        return rtnval

    def destroy(self, *, resource_group: str,
                run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned PPG in the ResourceGroup for the run.

            :param resource_group: ResourceGroup name.
            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of destroyed PPG names.
        """
        client = self._compute()
        deleted: List[str] = []
        try:
            listing = list(
                client.proximity_placement_groups.list_by_resource_group(
                    resource_group_name=resource_group
                )
            )
        except Exception:
            rtnval = deleted
            return rtnval

        for ppg in listing:
            if not belongs_to_run(azure_tags=getattr(ppg, "tags", None),
                                  run_id=run_id):
                continue
            ppg_name = getattr(ppg, "name", "")
            try:
                client.proximity_placement_groups.delete(
                    resource_group_name=resource_group,
                    proximity_placement_group_name=ppg_name,
                )
                deleted.append(ppg_name)
            except Exception:
                pass

        rtnval = deleted
        return rtnval
