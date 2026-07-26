"""
    .. module:: diskmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Azure Managed Disk manager for the Azure venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from ccai.provisioning.model.cloud.cloudstoragevolume import (
    CloudStorageVolume
)
from ccai.provisioning.model.cloud.storageclass import StorageClass
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


# Neutral StorageClass → Azure Managed Disk storage account type.
_STORAGE_CLASS_MAP: Dict[StorageClass, str] = {
    StorageClass.STANDARD: "StandardSSD_LRS",
    StorageClass.BALANCED: "StandardSSD_LRS",
    StorageClass.PERFORMANCE: "Premium_LRS",
    StorageClass.ARCHIVE: "Standard_LRS",
}


def map_storage_class(*, storage_class: StorageClass) -> str:
    """
        Map a neutral StorageClass to an Azure disk SKU name.

        :param storage_class: Neutral StorageClass member.

        :returns: Azure storage-account-type string.
    """
    rtnval = _STORAGE_CLASS_MAP.get(storage_class, "StandardSSD_LRS")
    return rtnval



from ccai.restclient.azure.azurearmerror import ResourceNotFoundError
from ccai.xmodules.xlogging.enhancedloggers import getEnhancedLogger

logger = getEnhancedLogger()

class DiskManager:
    """
        Manager for Azure Managed Disks.

        Disks are tagged with the venue owner/run/name tag triple.  When the
        neutral volume names an ``attached_to`` instance, the disk is
        attached as a data disk on that VM.
    """

    KIND: str = "volume"

    def __init__(self, *, session_factory: AzureSessionFactory) -> None:
        """
            Construct a DiskManager.

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

    def find(self, *, resource_group: str,
             name: str) -> Optional[Any]:
        """
            Find an existing owned managed disk by name.

            :param resource_group: ResourceGroup name.
            :param name: Neutral volume name.

            :returns: The Disk object, or None.
        """
        client = self._compute()
        rtnval = get_or_none(getter=client.disks.get,
                             resource_group_name=resource_group,
                             disk_name=name)
        return rtnval

    def ensure(self, *, desired: CloudStorageVolume, resource_group: str,
               location: str, run_id: str,
               default_tags: List[Dict[str, str]],
               attach_vm_name: Optional[str],
               aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for a managed disk.

            :param desired: Desired CloudStorageVolume.
            :param resource_group: ResourceGroup name.
            :param location: Azure location.
            :param run_id: Run identifier (used for owner tagging).
            :param default_tags: Venue default tags.
            :param attach_vm_name: VM name to attach the disk to, or None.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the disk.
        """
        client = self._compute()
        existing = self.find(resource_group=resource_group,
                             name=desired.name)
        disk_sku = map_storage_class(storage_class=desired.storage_class)

        if existing is None:
            tags = azure_tags_for(run_id=run_id, resource_name=desired.name,
                                  resource_kind=self.KIND,
                                  extra=dict(desired.tags),
                                  defaults=default_tags)
            params: Dict[str, Any] = {
                "location": location,
                "sku": {"name": disk_sku},
                "disk_size_gb": desired.size_gb,
                "creation_data": {"create_option": "Empty"},
                "tags": tags,
            }
            poller = client.disks.begin_create_or_update(
                resource_group_name=resource_group, disk_name=desired.name,
                disk=params,
            )
            existing = resolve_poller(poller=poller, aspects=aspects,
                                      description="create disk {}".format(
                                          desired.name
                                      ))

        disk_id = getattr(existing, "id", desired.name)

        attributes: Dict[str, Any] = {}
        attributes["disk_name"] = desired.name
        attributes["resource_group"] = resource_group
        attributes["disk_sku"] = disk_sku
        attributes["size_gb"] = desired.size_gb
        if attach_vm_name is not None and len(attach_vm_name) > 0:
            attributes["attached_to"] = attach_vm_name

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=disk_id,
            attributes=attributes,
            tags=from_azure(azure_tags=getattr(existing, "tags", None)),
        )
        return rtnval

    def destroy(self, *, resource_group: str,
                run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned managed disk in the ResourceGroup.

            :param resource_group: ResourceGroup name.
            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of destroyed disk names.
        """
        client = self._compute()
        deleted: List[str] = []
        try:
            listing = list(client.disks.list_by_resource_group(
                resource_group_name=resource_group
            ))
        except ResourceNotFoundError:
            # Resource group / listing target absent -> nothing owned.
            rtnval = deleted
            return rtnval
        except Exception as xcpt:
            # Do NOT mask a transient/auth/list failure as 'nothing owned';
            # that under-reports ownership and corrupts inventory/destroy.
            logger.warning("Failed to list Azure %s in resource_group=%s: %s" % (self.KIND, resource_group, xcpt))
            raise

        for disk in listing:
            if not belongs_to_run(azure_tags=getattr(disk, "tags", None),
                                  run_id=run_id):
                continue
            disk_name = getattr(disk, "name", "")
            try:
                client.disks.begin_delete(
                    resource_group_name=resource_group,
                    disk_name=disk_name,
                )
                deleted.append(disk_name)
            except Exception:
                pass

        rtnval = deleted
        return rtnval

    def list_owned(self, *, resource_group: str,
                   run_id: str) -> List[ProvisionedResource]:
        """
            Return every owned managed disk in the ResourceGroup for the run.

            :param resource_group: ResourceGroup name.
            :param run_id: Run identifier.

            :returns: List of ProvisionedResource entries.
        """
        client = self._compute()
        out: List[ProvisionedResource] = []
        try:
            listing = list(client.disks.list_by_resource_group(
                resource_group_name=resource_group
            ))
        except ResourceNotFoundError:
            # Resource group / listing target absent -> nothing owned.
            rtnval = out
            return rtnval
        except Exception as xcpt:
            # Do NOT mask a transient/auth/list failure as 'nothing owned';
            # that under-reports ownership and corrupts inventory/destroy.
            logger.warning("Failed to list Azure %s in resource_group=%s: %s" % (self.KIND, resource_group, xcpt))
            raise

        for disk in listing:
            live_tags = getattr(disk, "tags", None)
            if not belongs_to_run(azure_tags=live_tags, run_id=run_id):
                continue
            attributes: Dict[str, Any] = {}
            attributes["disk_name"] = getattr(disk, "name", "")
            attributes["resource_group"] = resource_group
            attributes["size_gb"] = getattr(disk, "disk_size_gb", 0)
            out.append(ProvisionedResource(
                kind=self.KIND, name=getattr(disk, "name", ""),
                venue_id=getattr(disk, "id", getattr(disk, "name", "x")),
                attributes=attributes,
                tags=from_azure(azure_tags=live_tags),
            ))

        rtnval = out
        return rtnval
