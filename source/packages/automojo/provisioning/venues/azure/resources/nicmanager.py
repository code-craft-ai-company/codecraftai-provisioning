"""
    .. module:: nicmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Azure Network Interface (NIC) manager for the Azure venue.

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
    belongs_to_run, get_or_none
)
from automojo.provisioning.venues.azure.azuresessionfactory import (
    AzureSessionFactory
)
from automojo.provisioning.venues.azure.azuretagging import (
    azure_tags_for, from_azure
)
from automojo.provisioning.venues.azure.azuretask import resolve_poller


class NicManager:
    """
        Manager for Azure Network Interfaces.

        Azure VMs require an explicit NIC; one NIC is created per VM and
        bound to the VM's subnet (and optional public IP).  NICs are tagged
        with the venue owner/run/name tag triple.
    """

    KIND: str = "nic"

    def __init__(self, *, session_factory: AzureSessionFactory) -> None:
        """
            Construct a NicManager.

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

    def _nic_name(self, *, instance_name: str) -> str:
        """
            Build the NIC name derived from the owning instance.

            :param instance_name: Neutral instance name.

            :returns: The NIC name.
        """
        rtnval = "{}-nic".format(instance_name)
        return rtnval

    def find(self, *, resource_group: str,
             instance_name: str) -> Optional[Any]:
        """
            Find an existing NIC for an instance.

            :param resource_group: ResourceGroup name.
            :param instance_name: Neutral instance name.

            :returns: The NetworkInterface object, or None.
        """
        client = self._network()
        rtnval = get_or_none(
            getter=client.network_interfaces.get,
            resource_group_name=resource_group,
            network_interface_name=self._nic_name(
                instance_name=instance_name
            ),
        )
        return rtnval

    def ensure(self, *, instance_name: str, resource_group: str,
               location: str, subnet_id: str, public_ip_id: Optional[str],
               run_id: str, default_tags: List[Dict[str, str]],
               aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for a VM NIC.

            :param instance_name: Neutral instance name.
            :param resource_group: ResourceGroup name.
            :param location: Azure location.
            :param subnet_id: Azure subnet id the NIC binds to.
            :param public_ip_id: Optional public-IP resource id, or None.
            :param run_id: Run identifier (used for owner tagging).
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the NIC.
        """
        client = self._network()
        nic_name = self._nic_name(instance_name=instance_name)
        existing = self.find(resource_group=resource_group,
                             instance_name=instance_name)

        if existing is None:
            ip_config: Dict[str, Any] = {
                "name": "{}-ipcfg".format(instance_name),
                "subnet": {"id": subnet_id},
                "private_ip_allocation_method": "Dynamic",
            }
            if public_ip_id is not None and len(public_ip_id) > 0:
                ip_config["public_ip_address"] = {"id": public_ip_id}

            tags = azure_tags_for(run_id=run_id, resource_name=nic_name,
                                  resource_kind=self.KIND,
                                  defaults=default_tags)
            params: Dict[str, Any] = {
                "location": location,
                "ip_configurations": [ip_config],
                "tags": tags,
            }
            poller = client.network_interfaces.begin_create_or_update(
                resource_group_name=resource_group,
                network_interface_name=nic_name,
                parameters=params,
            )
            existing = resolve_poller(poller=poller, aspects=aspects,
                                      description="create nic {}".format(
                                          nic_name
                                      ))

        attributes: Dict[str, Any] = {}
        attributes["nic_name"] = nic_name
        attributes["resource_group"] = resource_group
        attributes["subnet_id"] = subnet_id

        rtnval = ProvisionedResource(
            kind=self.KIND, name=nic_name,
            venue_id=getattr(existing, "id", nic_name),
            attributes=attributes,
            tags=from_azure(azure_tags=getattr(existing, "tags", None)),
        )
        return rtnval

    def list_owned(self, *, resource_group: str,
                   run_id: str) -> List[ProvisionedResource]:
        """
            Return every owned NIC in the ResourceGroup for the run.

            :param resource_group: ResourceGroup name.
            :param run_id: Run identifier.

            :returns: List of ProvisionedResource entries.
        """
        client = self._network()
        out: List[ProvisionedResource] = []
        try:
            listing = list(client.network_interfaces.list(
                resource_group_name=resource_group
            ))
        except Exception:
            rtnval = out
            return rtnval

        for nic in listing:
            live_tags = getattr(nic, "tags", None)
            if not belongs_to_run(azure_tags=live_tags, run_id=run_id):
                continue
            nic_name = getattr(nic, "name", "")
            attributes: Dict[str, Any] = {}
            attributes["nic_name"] = nic_name
            attributes["resource_group"] = resource_group
            out.append(ProvisionedResource(
                kind=self.KIND, name=nic_name,
                venue_id=getattr(nic, "id", nic_name),
                attributes=attributes,
                tags=from_azure(azure_tags=live_tags),
            ))

        rtnval = out
        return rtnval

    def destroy(self, *, resource_group: str,
                run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned NIC in the ResourceGroup for the run.

            :param resource_group: ResourceGroup name.
            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of destroyed NIC names.
        """
        client = self._network()
        deleted: List[str] = []
        try:
            listing = list(client.network_interfaces.list(
                resource_group_name=resource_group
            ))
        except Exception:
            rtnval = deleted
            return rtnval

        for nic in listing:
            if not belongs_to_run(azure_tags=getattr(nic, "tags", None),
                                  run_id=run_id):
                continue
            nic_name = getattr(nic, "name", "")
            try:
                client.network_interfaces.begin_delete(
                    resource_group_name=resource_group,
                    network_interface_name=nic_name,
                )
                deleted.append(nic_name)
            except Exception:
                pass

        rtnval = deleted
        return rtnval
