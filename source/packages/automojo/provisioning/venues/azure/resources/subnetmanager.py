"""
    .. module:: subnetmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Azure Subnet manager for the Azure venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.provisioning.model.cloud.cloudsubnet import CloudSubnet
from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.venues.azure.azureidempotency import get_or_none
from automojo.provisioning.venues.azure.azuresessionfactory import (
    AzureSessionFactory
)
from automojo.provisioning.venues.azure.azuretask import resolve_poller


class SubnetManager:
    """
        Manager for Azure Subnets.

        Subnets are children of a VNet; Azure subnets do not carry tags, so
        ownership is inferred from the enclosing run-id-tagged VNet.  An NSG
        association is applied when a security group id is supplied.
    """

    KIND: str = "subnet"

    def __init__(self, *, session_factory: AzureSessionFactory) -> None:
        """
            Construct a SubnetManager.

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

    def find(self, *, resource_group: str, vnet_name: str,
             name: str) -> Optional[Any]:
        """
            Find an existing subnet within a VNet by name.

            :param resource_group: ResourceGroup name.
            :param vnet_name: Parent VNet name.
            :param name: Neutral subnet name.

            :returns: The Subnet object, or None.
        """
        client = self._network()
        rtnval = get_or_none(getter=client.subnets.get,
                             resource_group_name=resource_group,
                             virtual_network_name=vnet_name,
                             subnet_name=name)
        return rtnval

    def ensure(self, *, desired: CloudSubnet, resource_group: str,
               vnet_name: str, nsg_id: Optional[str],
               aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for a subnet.

            :param desired: Desired CloudSubnet.
            :param resource_group: ResourceGroup name.
            :param vnet_name: Parent VNet name.
            :param nsg_id: Optional NSG id to associate, or None.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the subnet.
        """
        client = self._network()
        existing = self.find(resource_group=resource_group,
                             vnet_name=vnet_name, name=desired.name)

        if existing is None:
            params: Dict[str, Any] = {"address_prefix": desired.cidr}
            if nsg_id is not None and len(nsg_id) > 0:
                params["network_security_group"] = {"id": nsg_id}
            poller = client.subnets.begin_create_or_update(
                resource_group_name=resource_group,
                virtual_network_name=vnet_name,
                subnet_name=desired.name,
                subnet_parameters=params,
            )
            existing = resolve_poller(poller=poller, aspects=aspects,
                                      description="create subnet {}".format(
                                          desired.name
                                      ))

        attributes: Dict[str, Any] = {}
        attributes["subnet_name"] = desired.name
        attributes["vnet_name"] = vnet_name
        attributes["resource_group"] = resource_group
        attributes["cidr"] = desired.cidr
        attributes["public"] = desired.public

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name,
            venue_id=getattr(existing, "id", desired.name),
            attributes=attributes, tags=[],
        )
        return rtnval

    def destroy(self, *, resource_group: str, vnet_name: str,
                subnet_names: List[str], aspects: Any) -> List[str]:
        """
            Destroy the listed subnets within a VNet.

            :param resource_group: ResourceGroup name.
            :param vnet_name: Parent VNet name.
            :param subnet_names: Neutral subnet names to delete.
            :param aspects: Aspects.

            :returns: List of destroyed subnet names.
        """
        client = self._network()
        deleted: List[str] = []
        for subnet_name in subnet_names:
            try:
                client.subnets.begin_delete(
                    resource_group_name=resource_group,
                    virtual_network_name=vnet_name,
                    subnet_name=subnet_name,
                )
                deleted.append(subnet_name)
            except Exception:
                pass
        rtnval = deleted
        return rtnval
