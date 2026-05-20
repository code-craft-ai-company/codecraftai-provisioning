"""
    .. module:: resourcegroupmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Azure ResourceGroup manager — the apex container per apod.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.venues.azure.azureidempotency import (
    belongs_to_run, get_or_none, tag_dict_from_azure
)
from automojo.provisioning.venues.azure.azuresessionfactory import (
    AzureSessionFactory
)
from automojo.provisioning.venues.azure.azuretagging import (
    azure_tags_for, from_azure
)


class ResourceGroupManager:
    """
        Manager for the Azure ResourceGroup.

        The ResourceGroup is the apex container for an apod's resources.  It
        is created first on apply and removed last on destroy — and only
        when empty and owned by the run-id.
    """

    KIND: str = "resource_group"

    def __init__(self, *, session_factory: AzureSessionFactory) -> None:
        """
            Construct a ResourceGroupManager.

            :param session_factory: AzureSessionFactory.
        """
        self._session_factory: AzureSessionFactory = session_factory
        return

    def _resource(self) -> Any:
        """
            Return the ResourceManagementClient.

            :returns: A ResourceManagementClient.
        """
        rtnval = self._session_factory.resource_client()
        return rtnval

    def find(self, *, name: str) -> Optional[Any]:
        """
            Find a ResourceGroup by name.

            :param name: ResourceGroup name.

            :returns: The ResourceGroup object, or None.
        """
        client = self._resource()
        rtnval = get_or_none(getter=client.resource_groups.get,
                             resource_group_name=name)
        return rtnval

    def ensure(self, *, name: str, location: str, run_id: str,
               default_tags: List[Dict[str, str]],
               aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for the ResourceGroup.

            :param name: ResourceGroup name.
            :param location: Azure location for the group.
            :param run_id: Run identifier (used for owner tagging).
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the ResourceGroup.
        """
        client = self._resource()
        existing = self.find(name=name)

        if existing is None:
            tags = azure_tags_for(run_id=run_id, resource_name=name,
                                  resource_kind=self.KIND,
                                  defaults=default_tags)
            params: Dict[str, Any] = {"location": location, "tags": tags}
            existing = client.resource_groups.create_or_update(
                resource_group_name=name, parameters=params
            )

        live_tags = getattr(existing, "tags", None)

        attributes: Dict[str, Any] = {}
        attributes["resource_group"] = name
        attributes["location"] = getattr(existing, "location", location)

        rtnval = ProvisionedResource(
            kind=self.KIND, name=name,
            venue_id=getattr(existing, "id", name),
            attributes=attributes,
            tags=from_azure(azure_tags=live_tags),
        )
        return rtnval

    def matches(self, *, existing: Any, location: str) -> bool:
        """
            Compare an existing ResourceGroup to the desired location.

            :param existing: The live ResourceGroup object.
            :param location: Desired Azure location.

            :returns: True when the location matches.
        """
        rtnval = getattr(existing, "location", None) == location
        return rtnval

    def destroy(self, *, name: str, run_id: str, aspects: Any) -> bool:
        """
            Destroy the ResourceGroup when empty and owned by the run-id.

            :param name: ResourceGroup name.
            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: True when the ResourceGroup was deleted.
        """
        client = self._resource()
        existing = self.find(name=name)
        if existing is None:
            rtnval = False
            return rtnval

        live_tags = tag_dict_from_azure(
            azure_tags=getattr(existing, "tags", None)
        )
        if not belongs_to_run(azure_tags=live_tags, run_id=run_id):
            rtnval = False
            return rtnval

        # Only remove the group when no resources remain inside it.
        remaining = list(
            client.resources.list_by_resource_group(resource_group_name=name)
        )
        if len(remaining) > 0:
            rtnval = False
            return rtnval

        try:
            client.resource_groups.begin_delete(resource_group_name=name)
        except Exception:
            rtnval = False
            return rtnval

        rtnval = True
        return rtnval

    def list_owned(self, *, name: str,
                   run_id: str) -> List[ProvisionedResource]:
        """
            Return the ResourceGroup as a ProvisionedResource when owned.

            :param name: ResourceGroup name.
            :param run_id: Run identifier.

            :returns: A single-element list, or empty when not owned.
        """
        existing = self.find(name=name)
        out: List[ProvisionedResource] = []
        if existing is None:
            rtnval = out
            return rtnval

        live_tags = getattr(existing, "tags", None)
        if not belongs_to_run(azure_tags=live_tags, run_id=run_id):
            rtnval = out
            return rtnval

        attributes: Dict[str, Any] = {}
        attributes["resource_group"] = name
        attributes["location"] = getattr(existing, "location", "")
        out.append(ProvisionedResource(
            kind=self.KIND, name=name,
            venue_id=getattr(existing, "id", name),
            attributes=attributes,
            tags=from_azure(azure_tags=live_tags),
        ))
        rtnval = out
        return rtnval
