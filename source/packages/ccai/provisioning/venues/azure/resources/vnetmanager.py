"""
    .. module:: vnetmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Azure Virtual Network (VNet) manager for the Azure venue.

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
from ccai.provisioning.venues.azure.azureidempotency import (
    belongs_to_run, get_or_none
)
from ccai.provisioning.venues.azure.azuresessionfactory import (
    AzureSessionFactory
)
from ccai.provisioning.venues.azure.azuretagging import (
    azure_tags_for, from_azure
)
from ccai.provisioning.venues.azure.azuretask import resolve_poller


class VnetManager:
    """
        Manager for Azure Virtual Networks.

        VNets are tagged with the venue owner/run/name tag triple.
        Idempotent ``ensure`` reads the VNet by name and only mutates when
        absent or drifted.
    """

    KIND: str = "network"

    def __init__(self, *, session_factory: AzureSessionFactory) -> None:
        """
            Construct a VnetManager.

            :param session_factory: AzureSessionFactory.
        """
        self._session_factory: AzureSessionFactory = session_factory
        return

    def _network(self) -> Any:
        """
            Return the NetworkManagementClient.

            :returns: A NetworkManagementClient.
        """
        rtnval = self._session_factory.network_client()
        return rtnval

    def find(self, *, resource_group: str,
             name: str) -> Optional[Any]:
        """
            Find an existing VNet by name and verify run ownership.

            :param resource_group: ResourceGroup name.
            :param name: Neutral network name.

            :returns: The VirtualNetwork object, or None.
        """
        client = self._network()
        existing = get_or_none(getter=client.virtual_networks.get,
                               resource_group_name=resource_group,
                               virtual_network_name=name)
        rtnval = existing
        return rtnval

    def matches(self, *, existing: Any, desired: CloudNetwork) -> bool:
        """
            Compare an existing VNet to the desired CloudNetwork.

            :param existing: The live VirtualNetwork object.
            :param desired: Desired CloudNetwork.

            :returns: True when the address prefixes match.
        """
        address_space = getattr(existing, "address_space", None)
        prefixes: List[str] = []
        if address_space is not None:
            prefixes = list(getattr(address_space, "address_prefixes", []) or [])
        rtnval = desired.cidr in prefixes
        return rtnval

    def ensure(self, *, desired: CloudNetwork, resource_group: str,
               location: str, run_id: str,
               default_tags: List[Dict[str, str]],
               aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for a VNet.

            :param desired: Desired CloudNetwork.
            :param resource_group: ResourceGroup name.
            :param location: Azure location.
            :param run_id: Run identifier (used for owner tagging).
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the VNet.
        """
        client = self._network()
        existing = self.find(resource_group=resource_group,
                             name=desired.name)

        if existing is None:
            tags = azure_tags_for(run_id=run_id, resource_name=desired.name,
                                  resource_kind=self.KIND,
                                  extra=dict(desired.tags),
                                  defaults=default_tags)
            params: Dict[str, Any] = {
                "location": location,
                "address_space": {"address_prefixes": [desired.cidr]},
                "tags": tags,
            }
            poller = client.virtual_networks.begin_create_or_update(
                resource_group_name=resource_group,
                virtual_network_name=desired.name,
                parameters=params,
            )
            existing = resolve_poller(poller=poller, aspects=aspects,
                                      description="create vnet {}".format(
                                          desired.name
                                      ))

        attributes: Dict[str, Any] = {}
        attributes["vnet_name"] = desired.name
        attributes["resource_group"] = resource_group
        attributes["cidr"] = desired.cidr
        attributes["location"] = getattr(existing, "location", location)

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name,
            venue_id=getattr(existing, "id", desired.name),
            attributes=attributes,
            tags=from_azure(azure_tags=getattr(existing, "tags", None)),
        )
        return rtnval

    def destroy(self, *, resource_group: str,
                run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned VNet in the ResourceGroup for the run.

            :param resource_group: ResourceGroup name.
            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of destroyed VNet names.
        """
        client = self._network()
        deleted: List[str] = []
        try:
            listing = list(client.virtual_networks.list(
                resource_group_name=resource_group
            ))
        except Exception:
            rtnval = deleted
            return rtnval

        for vnet in listing:
            if not belongs_to_run(azure_tags=getattr(vnet, "tags", None),
                                  run_id=run_id):
                continue
            vnet_name = getattr(vnet, "name", "")
            try:
                client.virtual_networks.begin_delete(
                    resource_group_name=resource_group,
                    virtual_network_name=vnet_name,
                )
                deleted.append(vnet_name)
            except Exception:
                pass

        rtnval = deleted
        return rtnval

    def list_owned(self, *, resource_group: str,
                   run_id: str) -> List[ProvisionedResource]:
        """
            Return all owned VNets in the ResourceGroup for the run.

            :param resource_group: ResourceGroup name.
            :param run_id: Run identifier.

            :returns: List of ProvisionedResource entries.
        """
        client = self._network()
        out: List[ProvisionedResource] = []
        try:
            listing = list(client.virtual_networks.list(
                resource_group_name=resource_group
            ))
        except Exception:
            rtnval = out
            return rtnval

        for vnet in listing:
            live_tags = getattr(vnet, "tags", None)
            if not belongs_to_run(azure_tags=live_tags, run_id=run_id):
                continue
            attributes: Dict[str, Any] = {}
            attributes["vnet_name"] = getattr(vnet, "name", "")
            attributes["resource_group"] = resource_group
            out.append(ProvisionedResource(
                kind=self.KIND, name=getattr(vnet, "name", ""),
                venue_id=getattr(vnet, "id", getattr(vnet, "name", "x")),
                attributes=attributes,
                tags=from_azure(azure_tags=live_tags),
            ))

        rtnval = out
        return rtnval
