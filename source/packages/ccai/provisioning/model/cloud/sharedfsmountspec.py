"""
    .. module:: sharedfsmountspec
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Spec for mounting a shared filesystem onto an instance.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import List, Optional

from ccai.restclient.base.schemaobject import SchemaObject
from ccai.restclient.base.schemafield import Field

from ccai.provisioning.model.exceptions import SchemaValidationError
from ccai.provisioning.model.cloud.validators import validate_name


class SharedFsMountSpec(SchemaObject):
    """
        Mount declaration tying a shared filesystem to a target instance.
    """

    filesystem_name = Field(str, required=True)
    target_instance = Field(str, required=True)
    mount_path = Field(str, required=True)
    mount_options = Field(list, required=False, default=None)

    def __init__(self, *, filesystem_name: str, target_instance: str,
                 mount_path: str,
                 mount_options: Optional[List[str]] = None) -> None:
        """
            Construct a SharedFsMountSpec.

            :param filesystem_name: Name of the referenced CloudSharedFilesystem.
            :param target_instance: Name of the receiving CloudInstance.
            :param mount_path: Absolute mount path on the target.
            :param mount_options: Optional mount option strings.

            :raises: SchemaValidationError
        """
        validate_name(value=filesystem_name)
        validate_name(value=target_instance)

        if mount_path is None or len(mount_path) == 0:
            raise SchemaValidationError("mount_path must not be empty.")

        if not mount_path.startswith("/"):
            raise SchemaValidationError(
                "mount_path must be absolute, got {!r}".format(mount_path)
            )

        effective_options = mount_options if mount_options is not None else []

        super().__init__(filesystem_name=filesystem_name,
                         target_instance=target_instance,
                         mount_path=mount_path,
                         mount_options=effective_options)
        return
