"""
    .. module:: filestoragemanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: OCI File Storage manager (shared FS) for the Oracle Cloud venue.

    OCI realises shared-FS through File Storage (NFSv3 mount targets).  v1
    supports ``kind=VENUE_NATIVE`` (create-or-reuse a File Storage mount
    target) and ``kind=LUSTRE`` attach-only when ``existing_id`` is set.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Any, Dict

from automojo.provisioning.model.cloud.cloudsharedfilesystem import (
    CloudSharedFilesystem
)
from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.venues.oracle.ocisessionfactory import (
    OciSessionFactory
)
from automojo.provisioning.venues.oracle.ocierrors import OciValidationError


# OCI File Storage realises these neutral kinds.
_SUPPORTED_KINDS = frozenset({"VENUE_NATIVE", "LUSTRE", "FILESTORE"})

# Neutral kinds OCI cannot realise (substitution suggestions surfaced).
_REJECTED_KINDS = frozenset({"WEKA", "VAST", "GPFS", "BEEGFS", "EFS",
                             "AZUREFILES"})


class FileStorageManager:
    """
        Manager for OCI File Storage — attach-only in v1.

        v1 supports ``kind=VENUE_NATIVE`` (the native OCI File Storage
        offering) and ``kind=LUSTRE`` only when an ``existing_id`` is given
        (managed Lustre attach).  Other kinds are rejected with a
        substitution suggestion.
    """

    KIND: str = "shared_filesystem"

    def __init__(self, *, session_factory: OciSessionFactory) -> None:
        """
            Construct a FileStorageManager.

            :param session_factory: OciSessionFactory.
        """
        self._session_factory: OciSessionFactory = session_factory
        return

    def _fs(self) -> Any:
        """
            Return the OCI FileStorageClient.

            :returns: An ``oci`` FileStorageClient.
        """
        rtnval = self._session_factory.client(service_name="file_storage")
        return rtnval

    def attach(self, *, desired: CloudSharedFilesystem,
               aspects: Any) -> ProvisionedResource:
        """
            Attach to or reference an OCI File Storage shared filesystem.

            :param desired: The CloudSharedFilesystem.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the filesystem.
            :raises: OciValidationError
        """
        if desired.kind in _REJECTED_KINDS:
            err_msg_lines = [
                "OCI realises shared-FS through OCI File Storage."
            ]
            err_msg_lines.append("FILESYSTEM: {}".format(desired.name))
            err_msg_lines.append("KIND: {}".format(desired.kind))
            err_msg_lines.append(
                "GUIDANCE: substitute kind=VENUE_NATIVE for OCI File "
                "Storage, or kind=LUSTRE with existing_id to attach a "
                "managed Lustre filesystem."
            )
            err_msg = os.linesep.join(err_msg_lines)
            raise OciValidationError(err_msg)

        if desired.kind not in _SUPPORTED_KINDS:
            err_msg_lines = ["OCI File Storage cannot realise this kind."]
            err_msg_lines.append("FILESYSTEM: {}".format(desired.name))
            err_msg_lines.append("KIND: {}".format(desired.kind))
            err_msg = os.linesep.join(err_msg_lines)
            raise OciValidationError(err_msg)

        if desired.kind == "LUSTRE":
            if desired.existing_id is None or len(desired.existing_id) == 0:
                err_msg_lines = [
                    "OCI managed Lustre attach requires existing_id."
                ]
                err_msg_lines.append("FILESYSTEM: {}".format(desired.name))
                err_msg_lines.append(
                    "GUIDANCE: pre-provision the managed Lustre filesystem "
                    "and pass existing_id."
                )
                err_msg = os.linesep.join(err_msg_lines)
                raise OciValidationError(err_msg)

        attributes: Dict[str, Any] = {}
        attributes["kind"] = desired.kind
        venue_id = desired.name

        if desired.existing_id is not None and len(desired.existing_id) > 0:
            attributes["existing_id"] = desired.existing_id
            venue_id = desired.existing_id
            client = self._fs()
            try:
                response = client.get_file_system(
                    file_system_id=desired.existing_id
                )
                attributes["display_name"] = getattr(
                    response.data, "display_name", ""
                )
            except Exception:
                pass

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=venue_id,
            attributes=attributes, tags=[],
        )
        return rtnval
