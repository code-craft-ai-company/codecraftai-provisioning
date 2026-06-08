"""
    .. module:: fsxmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: AWS FSx for Lustre manager (attach-only in v1 per §7.6).

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Any, Dict

from ccai.provisioning.model.cloud.cloudsharedfilesystem import (
    CloudSharedFilesystem
)
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.venues.aws.awsboto3sessionfactory import (
    AwsBoto3SessionFactory
)
from ccai.provisioning.venues.aws.awserrors import AwsValidationError


class FsxManager:
    """
        Manager for FSx for Lustre — attach-only.

        v1 supports referencing an existing FSx file system via
        ``CloudSharedFilesystem.existing_id``; the manager looks it up and
        returns its DNS name + mount path data so the instance manager can
        render mount commands into cloud-init.
    """

    KIND: str = "shared_filesystem"

    def __init__(self, *, session_factory: AwsBoto3SessionFactory) -> None:
        """
            Construct an FsxManager.

            :param session_factory: AwsBoto3SessionFactory.
        """
        self._session_factory: AwsBoto3SessionFactory = session_factory
        return

    def _fsx(self) -> Any:
        rtnval = self._session_factory.client(service_name="fsx")
        return rtnval

    def attach(self, *, desired: CloudSharedFilesystem,
               aspects: Any) -> ProvisionedResource:
        """
            Attach to an existing FSx for Lustre filesystem.

            :param desired: The CloudSharedFilesystem.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the attached filesystem.
            :raises: AwsValidationError
        """
        if desired.kind != "LUSTRE":
            err_msg_lines = ["FsxManager only supports LUSTRE filesystems."]
            err_msg_lines.append("FILESYSTEM: {}".format(desired.name))
            err_msg_lines.append("KIND: {}".format(desired.kind))
            err_msg = os.linesep.join(err_msg_lines)
            raise AwsValidationError(err_msg)

        if desired.existing_id is None or len(desired.existing_id) == 0:
            err_msg_lines = [
                "FSx for Lustre provision path is not supported in v1."
            ]
            err_msg_lines.append("FILESYSTEM: {}".format(desired.name))
            err_msg_lines.append(
                "GUIDANCE: pre-provision the FSx filesystem and pass "
                "existing_id; v1.5 will add the provision-and-attach path."
            )
            err_msg = os.linesep.join(err_msg_lines)
            raise AwsValidationError(err_msg)

        client = self._fsx()
        dns_name = ""
        mount_name = ""
        try:
            response = client.describe_file_systems(
                FileSystemIds=[desired.existing_id]
            )
            entries = response.get("FileSystems", [])
            if len(entries) > 0:
                dns_name = entries[0].get("DNSName", "")
                lustre = entries[0].get("LustreConfiguration", {})
                mount_name = lustre.get("MountName", "")
        except Exception:
            pass

        attributes: Dict[str, Any] = {}
        attributes["existing_id"] = desired.existing_id
        attributes["dns_name"] = dns_name
        attributes["mount_name"] = mount_name
        attributes["kind"] = desired.kind

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name,
            venue_id=desired.existing_id,
            attributes=attributes, tags={},
        )
        return rtnval
