"""
    .. module:: lustremanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Azure Managed Lustre / Azure NetApp Files attach-only manager.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Any, Dict

from ccai.interfaces.cloudsharedfilesystem import (
    CloudSharedFilesystem
)
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.venues.azure.azureerrors import AzureValidationError
from ccai.provisioning.venues.azure.azuresessionfactory import (
    AzureSessionFactory
)


# Shared-FS kinds the Azure venue realises.
_SUPPORTED_KINDS = frozenset({"LUSTRE", "AZUREFILES"})


class LustreManager:
    """
        Manager for Azure Managed Lustre and Azure NetApp Files — attach
        only.

        v1 supports referencing an existing file system via
        ``CloudSharedFilesystem.existing_id``; the manager records it as a
        :class:`ProvisionedResource` so the VM manager can render fstab /
        NFSv4.1 mounts into cloud-init.  WEKA / VAST / GPFS / BeeGFS are
        rejected with a substitution pointer.
    """

    KIND: str = "shared_filesystem"

    def __init__(self, *, session_factory: AzureSessionFactory) -> None:
        """
            Construct a LustreManager.

            :param session_factory: AzureSessionFactory.
        """
        self._session_factory: AzureSessionFactory = session_factory
        return

    def attach(self, *, desired: CloudSharedFilesystem,
               aspects: Any) -> ProvisionedResource:
        """
            Attach to an existing Azure Managed Lustre or ANF file system.

            :param desired: The CloudSharedFilesystem.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the attached FS.
            :raises: AzureValidationError
        """
        if desired.kind not in _SUPPORTED_KINDS:
            err_msg_lines = [
                "Azure realises shared-FS through Azure Managed Lustre "
                "(kind=LUSTRE) or Azure NetApp Files (kind=AZUREFILES)."
            ]
            err_msg_lines.append("FILESYSTEM: {}".format(desired.name))
            err_msg_lines.append("KIND: {}".format(desired.kind))
            err_msg = os.linesep.join(err_msg_lines)
            raise AzureValidationError(err_msg)

        if desired.existing_id is None or len(desired.existing_id) == 0:
            err_msg_lines = [
                "Azure shared-FS provision path is not supported in v1."
            ]
            err_msg_lines.append("FILESYSTEM: {}".format(desired.name))
            err_msg_lines.append(
                "GUIDANCE: pre-provision the Azure Managed Lustre / ANF "
                "filesystem and pass existing_id; v1.5 will add the "
                "provision-and-attach path."
            )
            err_msg = os.linesep.join(err_msg_lines)
            raise AzureValidationError(err_msg)

        if desired.kind == "AZUREFILES":
            mount_protocol = "nfsv4.1"
        else:
            mount_protocol = "lustre"

        attributes: Dict[str, Any] = {}
        attributes["existing_id"] = desired.existing_id
        attributes["kind"] = desired.kind
        attributes["mount_protocol"] = mount_protocol

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name,
            venue_id=desired.existing_id,
            attributes=attributes, tags={},
        )
        return rtnval
