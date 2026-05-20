"""
    .. module:: workloadjob
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Declarative WorkloadJob resource.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.restclient.base.schemaobject import SchemaObject
from automojo.restclient.base.schemafield import Field

from automojo.provisioning.model.exceptions import SchemaValidationError
from automojo.provisioning.model.cloud.validators import (
    validate_name, validate_positive_int
)
from automojo.provisioning.model.cloud.cloudacceleratorspec import (
    CloudAcceleratorSpec
)
from automojo.provisioning.model.cloud.sharedfsmountspec import SharedFsMountSpec


_SUPPORTED_RESTART_POLICIES = ("Never", "OnFailure")


class WorkloadJob(SchemaObject):
    """
        Declarative batch-style workload (single execution, terminal completion).
    """

    name = Field(str, required=True)
    image = Field(str, required=True)
    command = Field(list, required=False, default=None)
    resources = Field(dict, required=False, default=None)
    accelerators = Field(list, required=False, default=None)
    replicas = Field(int, required=False, default=1)
    restart_policy = Field(str, required=False, default="Never")
    env = Field(dict, required=False, default=None)
    shared_fs_mounts = Field(list, required=False, default=None)
    network = Field(str, required=False, default=None)

    def __init__(self, *, name: str, image: str,
                 command: Optional[List[str]] = None,
                 resources: Optional[Dict[str, Any]] = None,
                 accelerators: Optional[List[CloudAcceleratorSpec]] = None,
                 replicas: int = 1,
                 restart_policy: str = "Never",
                 env: Optional[Dict[str, str]] = None,
                 shared_fs_mounts: Optional[List[SharedFsMountSpec]] = None,
                 network: Optional[str] = None) -> None:
        """
            Construct a WorkloadJob.

            :param name: Job name.
            :param image: Container image reference.
            :param command: Optional command argv list.
            :param resources: Optional resources dict (cpu, memory hints).
            :param accelerators: Optional accelerator specs.
            :param replicas: Replica count; must be > 0.
            :param restart_policy: Never or OnFailure.
            :param env: Optional environment variable map.
            :param shared_fs_mounts: Optional shared filesystem mounts.
            :param network: Optional network reference.

            :raises: SchemaValidationError
        """
        validate_name(value=name)

        if image is None or len(image) == 0:
            raise SchemaValidationError("image must not be empty.")

        validate_positive_int(value=replicas, field_name="replicas")

        if restart_policy not in _SUPPORTED_RESTART_POLICIES:
            raise SchemaValidationError(
                "restart_policy must be one of {}, got {!r}".format(
                    ", ".join(_SUPPORTED_RESTART_POLICIES), restart_policy
                )
            )

        effective_command = command if command is not None else []
        effective_resources = resources if resources is not None else {}
        effective_env = env if env is not None else {}

        super().__init__(name=name, image=image, command=effective_command,
                         resources=effective_resources,
                         accelerators=accelerators, replicas=replicas,
                         restart_policy=restart_policy, env=effective_env,
                         shared_fs_mounts=shared_fs_mounts, network=network)
        return
