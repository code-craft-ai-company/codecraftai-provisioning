"""
    .. module:: workloadservice
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Declarative long-running WorkloadService resource.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from ccai.interfaces.schemaobject import SchemaObject
from ccai.interfaces.schemafield import Field

from ccai.interfaces.schemavalidationerror import SchemaValidationError
from ccai.interfaces.schemavalidators import (
    validate_name, validate_positive_int
)
from ccai.interfaces.cloudacceleratorspec import (
    CloudAcceleratorSpec
)
from ccai.interfaces.sharedfsmountspec import SharedFsMountSpec


_SUPPORTED_EXPOSURES = ("ClusterIP", "LoadBalancer", "NodePort")


class WorkloadService(SchemaObject):
    """
        Declarative long-running service workload (deployment + service).
    """

    name = Field(str, required=True)
    image = Field(str, required=True)
    command = Field(list, required=False, default=None)
    resources = Field(dict, required=False, default=None)
    accelerators = Field(list, required=False, default=None)
    replicas = Field(int, required=False, default=1)
    ports = Field(list, required=False, default=None)
    env = Field(dict, required=False, default=None)
    shared_fs_mounts = Field(list, required=False, default=None)
    exposure = Field(str, required=False, default="ClusterIP")

    def __init__(self, *, name: str, image: str,
                 command: Optional[List[str]] = None,
                 resources: Optional[Dict[str, Any]] = None,
                 accelerators: Optional[List[CloudAcceleratorSpec]] = None,
                 replicas: int = 1,
                 ports: Optional[List[Dict[str, Any]]] = None,
                 env: Optional[Dict[str, str]] = None,
                 shared_fs_mounts: Optional[List[SharedFsMountSpec]] = None,
                 exposure: str = "ClusterIP") -> None:
        """
            Construct a WorkloadService.

            :param name: Service name.
            :param image: Container image reference.
            :param command: Optional command argv list.
            :param resources: Optional resources dict (cpu, memory hints).
            :param accelerators: Optional accelerator specs.
            :param replicas: Replica count; must be > 0.
            :param ports: Optional list of port dicts.
            :param env: Optional environment variable map.
            :param shared_fs_mounts: Optional shared filesystem mounts.
            :param exposure: ClusterIP | LoadBalancer | NodePort.

            :raises: SchemaValidationError
        """
        validate_name(value=name)

        if image is None or len(image) == 0:
            raise SchemaValidationError("image must not be empty.")

        validate_positive_int(value=replicas, field_name="replicas")

        if exposure not in _SUPPORTED_EXPOSURES:
            raise SchemaValidationError(
                "exposure must be one of {}, got {!r}".format(
                    ", ".join(_SUPPORTED_EXPOSURES), exposure
                )
            )

        effective_command = command if command is not None else []
        effective_resources = resources if resources is not None else {}
        effective_ports = ports if ports is not None else []
        effective_env = env if env is not None else {}

        super().__init__(name=name, image=image, command=effective_command,
                         resources=effective_resources,
                         accelerators=accelerators, replicas=replicas,
                         ports=effective_ports, env=effective_env,
                         shared_fs_mounts=shared_fs_mounts, exposure=exposure)
        return
