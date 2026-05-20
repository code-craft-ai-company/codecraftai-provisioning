"""
    .. module:: blobmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Azure Blob storage manager (Storage Account + Blob Container).

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.provisioning.model.cloud.cloudobjectbucket import (
    CloudObjectBucket
)
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


def storage_account_name(*, run_id: str, name: str) -> str:
    """
        Build a DNS-safe Azure Storage Account name.

        Azure storage account names must be 3-24 lowercase alphanumerics.

        :param run_id: Run identifier.
        :param name: Neutral bucket name.

        :returns: A DNS-safe storage account name (truncated to 24 chars).
    """
    raw = "amj{}{}".format(run_id, name)
    sanitized = "".join(ch for ch in raw.lower() if ch.isalnum())
    rtnval = sanitized[:24]
    return rtnval


class BlobManager:
    """
        Manager for Azure Blob storage.

        A neutral :class:`CloudObjectBucket` maps to a Storage Account that
        hosts a single Blob Container.  The Storage Account carries the
        venue owner/run/name tags; the container inherits ownership from it.
    """

    KIND: str = "bucket"

    def __init__(self, *, session_factory: AzureSessionFactory) -> None:
        """
            Construct a BlobManager.

            :param session_factory: AzureSessionFactory.
        """
        self._session_factory: AzureSessionFactory = session_factory
        return

    def _storage(self) -> Any:
        """
            Return the StorageManagementClient.

            :returns: A StorageManagementClient.
        """
        rtnval = self._session_factory.storage_client()
        return rtnval

    def find(self, *, resource_group: str,
             account_name: str) -> Optional[Any]:
        """
            Find an existing storage account by name.

            :param resource_group: ResourceGroup name.
            :param account_name: Azure storage account name.

            :returns: The StorageAccount object, or None.
        """
        client = self._storage()
        rtnval = get_or_none(getter=client.storage_accounts.get_properties,
                             resource_group_name=resource_group,
                             account_name=account_name)
        return rtnval

    def ensure(self, *, desired: CloudObjectBucket, resource_group: str,
               location: str, run_id: str,
               default_tags: List[Dict[str, str]],
               aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for a Blob container.

            :param desired: Desired CloudObjectBucket.
            :param resource_group: ResourceGroup name.
            :param location: Azure location.
            :param run_id: Run identifier (used for owner tagging).
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the container.
        """
        client = self._storage()
        account = storage_account_name(run_id=run_id, name=desired.name)
        existing = self.find(resource_group=resource_group,
                             account_name=account)

        if existing is None:
            tags = azure_tags_for(run_id=run_id, resource_name=desired.name,
                                  resource_kind=self.KIND,
                                  extra=list(desired.tags),
                                  defaults=default_tags)
            params: Dict[str, Any] = {
                "location": location,
                "sku": {"name": "Standard_LRS"},
                "kind": "StorageV2",
                "tags": tags,
            }
            poller = client.storage_accounts.begin_create(
                resource_group_name=resource_group, account_name=account,
                parameters=params,
            )
            existing = resolve_poller(
                poller=poller, aspects=aspects,
                description="create storage account {}".format(account),
            )

        container_name = desired.name.lower().replace("_", "-")
        try:
            client.blob_containers.create(
                resource_group_name=resource_group, account_name=account,
                container_name=container_name, blob_container={},
            )
        except Exception:
            pass

        attributes: Dict[str, Any] = {}
        attributes["storage_account"] = account
        attributes["container_name"] = container_name
        attributes["resource_group"] = resource_group
        attributes["versioning"] = desired.versioning

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name,
            venue_id=getattr(existing, "id", account),
            attributes=attributes,
            tags=from_azure(azure_tags=getattr(existing, "tags", None)),
        )
        return rtnval

    def destroy(self, *, resource_group: str,
                run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned storage account in the ResourceGroup.

            :param resource_group: ResourceGroup name.
            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of destroyed storage account names.
        """
        client = self._storage()
        deleted: List[str] = []
        try:
            listing = list(client.storage_accounts.list_by_resource_group(
                resource_group_name=resource_group
            ))
        except Exception:
            rtnval = deleted
            return rtnval

        for account in listing:
            if not belongs_to_run(azure_tags=getattr(account, "tags", None),
                                  run_id=run_id):
                continue
            account_name = getattr(account, "name", "")
            try:
                client.storage_accounts.delete(
                    resource_group_name=resource_group,
                    account_name=account_name,
                )
                deleted.append(account_name)
            except Exception:
                pass

        rtnval = deleted
        return rtnval

    def list_owned(self, *, resource_group: str,
                   run_id: str) -> List[ProvisionedResource]:
        """
            Return every owned storage account in the ResourceGroup.

            :param resource_group: ResourceGroup name.
            :param run_id: Run identifier.

            :returns: List of ProvisionedResource entries.
        """
        client = self._storage()
        out: List[ProvisionedResource] = []
        try:
            listing = list(client.storage_accounts.list_by_resource_group(
                resource_group_name=resource_group
            ))
        except Exception:
            rtnval = out
            return rtnval

        for account in listing:
            live_tags = getattr(account, "tags", None)
            if not belongs_to_run(azure_tags=live_tags, run_id=run_id):
                continue
            flat = live_tags if isinstance(live_tags, dict) else {}
            neutral_name = flat.get("automojo:resource-name", "")
            if len(neutral_name) == 0:
                continue
            attributes: Dict[str, Any] = {}
            attributes["storage_account"] = getattr(account, "name", "")
            attributes["resource_group"] = resource_group
            out.append(ProvisionedResource(
                kind=self.KIND, name=neutral_name,
                venue_id=getattr(account, "id",
                                 getattr(account, "name", "x")),
                attributes=attributes,
                tags=from_azure(azure_tags=live_tags),
            ))

        rtnval = out
        return rtnval
