"""
    .. module:: cloudprovisionerregistry
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Registry mapping venue names to CloudProvisioner instances.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Dict, List, Optional

from ccai.provisioning.model.exceptions import SchemaValidationError
from ccai.provisioning.model.cloud.cloudprovisioner import CloudProvisioner


class CloudProvisionerRegistry:
    """
        Small dict-based registry from venue name to CloudProvisioner.

        Venues themselves land in M7+; the engine consumes whatever the
        caller has registered.  Lookups raise SchemaValidationError when
        a venue name is missing — the engine never silently skips a venue.
    """

    def __init__(self,
                 *, entries: Optional[Dict[str, CloudProvisioner]] = None
                 ) -> None:
        """
            Construct a CloudProvisionerRegistry.

            :param entries: Optional initial venue-name -> provisioner map.
        """
        self._entries: Dict[str, CloudProvisioner] = {}
        if entries is not None:
            for name, prov in entries.items():
                self.register(name=name, provisioner=prov)
        return

    def register(self, *, name: str,
                 provisioner: CloudProvisioner) -> None:
        """
            Register a provisioner for a venue name.

            :param name: Venue name.
            :param provisioner: A CloudProvisioner instance.

            :raises: SchemaValidationError
        """
        if name is None or len(name) == 0:
            raise SchemaValidationError("venue name must not be empty.")
        if not isinstance(provisioner, CloudProvisioner):
            raise SchemaValidationError(
                "provisioner must be a CloudProvisioner instance."
            )
        self._entries[name] = provisioner
        return

    def get(self, *, name: str) -> CloudProvisioner:
        """
            Return the provisioner registered under name.

            :param name: Venue name.

            :returns: The CloudProvisioner instance.
            :raises: SchemaValidationError
        """
        if name not in self._entries:
            err_msg_lines = ["No CloudProvisioner registered for venue."]
            err_msg_lines.append("REQUESTED: {!r}".format(name))
            err_msg_lines.append(
                "REGISTERED: {}".format(sorted(self._entries.keys()))
            )
            err_msg = os.linesep.join(err_msg_lines)
            raise SchemaValidationError(err_msg)
        rtnval = self._entries[name]
        return rtnval

    def names(self) -> List[str]:
        """
            Return the registered venue names.

            :returns: Sorted list of names.
        """
        rtnval = sorted(self._entries.keys())
        return rtnval

    def items(self) -> List:
        """
            Return ``(name, provisioner)`` pairs in registration order.

            :returns: List of (name, provisioner) tuples.
        """
        rtnval = list(self._entries.items())
        return rtnval

    def __len__(self) -> int:
        """
            Return registry size.

            :returns: Number of registered provisioners.
        """
        rtnval = len(self._entries)
        return rtnval
