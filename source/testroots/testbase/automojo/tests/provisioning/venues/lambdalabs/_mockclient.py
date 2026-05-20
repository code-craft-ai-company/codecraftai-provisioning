"""
    .. module:: _mockclient
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: MockLambdalabsClient — an in-memory stand-in for the Lambda
               Labs interop client used by the venue test suite.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List

from automojo.restclient.lambdalabs.model.lambdalabscluster import (
    LambdalabsCluster
)
from automojo.restclient.lambdalabs.model.lambdalabsfilesystem import (
    LambdalabsFilesystem
)
from automojo.restclient.lambdalabs.model.lambdalabsinstance import (
    LambdalabsInstance
)
from automojo.restclient.lambdalabs.model.lambdalabssshkey import LambdalabsSshKey
from automojo.restclient.lambdalabs.model.lambdalabsterminationresult import (
    LambdalabsTerminationResult
)


class MockLambdalabsClient:
    """
        In-memory stand-in for :class:`LambdalabsClient`.

        Holds deterministic dictionaries for SSH keys, instances, file
        systems, and clusters so the venue provisioner can be exercised
        without any HTTP traffic.  Mutating calls update the in-memory
        state so apply / destroy idempotence can be observed.
    """

    def __init__(self) -> None:
        """
            Construct an empty MockLambdalabsClient.
        """
        self._ssh_keys: Dict[str, LambdalabsSshKey] = {}
        self._instances: Dict[str, LambdalabsInstance] = {}
        self._filesystems: Dict[str, LambdalabsFilesystem] = {}
        self._clusters: Dict[str, LambdalabsCluster] = {}
        self._counter = 0
        self.launch_calls = 0
        self.cluster_calls = 0
        self.register_calls = 0
        self.terminate_calls = 0
        return

    def _next_id(self, *, prefix: str) -> str:
        """
            Allocate a deterministic identifier.

            :param prefix: The identifier prefix.

            :returns: A new identifier string.
        """
        self._counter = self._counter + 1
        rtnval = "{}-{}".format(prefix, self._counter)
        return rtnval

    def seed_filesystem(self, *, identifier: str, name: str,
                        region: str) -> None:
        """
            Seed an existing file system into the mock state.

            :param identifier: The file-system id.
            :param name: The file-system name.
            :param region: The file-system region.

            :returns: ``None``.
        """
        self._filesystems[identifier] = LambdalabsFilesystem(
            identifier=identifier, name=name, region=region
        )
        return

    # -- ssh keys ------------------------------------------------------

    def list_ssh_keys(self, *, aspects: Any) -> List[LambdalabsSshKey]:
        """
            List the registered SSH keys.

            :param aspects: Behaviour control (unused).

            :returns: The SSH key list.
        """
        rtnval = list(self._ssh_keys.values())
        return rtnval

    def register_ssh_key(self, *, name: str, public_key: str,
                         aspects: Any) -> LambdalabsSshKey:
        """
            Register an SSH key (idempotent by name).

            :param name: The key name.
            :param public_key: The public key material.
            :param aspects: Behaviour control (unused).

            :returns: The registered or pre-existing key.
        """
        for key in self._ssh_keys.values():
            if key.name == name:
                rtnval = key
                return rtnval
        self.register_calls = self.register_calls + 1
        key_id = self._next_id(prefix="key")
        key = LambdalabsSshKey(identifier=key_id, name=name,
                               public_key=public_key)
        self._ssh_keys[key_id] = key
        rtnval = key
        return rtnval

    # -- file systems --------------------------------------------------

    def list_filesystems(self, *, aspects: Any) -> List[LambdalabsFilesystem]:
        """
            List the file systems.

            :param aspects: Behaviour control (unused).

            :returns: The file-system list.
        """
        rtnval = list(self._filesystems.values())
        return rtnval

    # -- instances -----------------------------------------------------

    def list_instances(self, *, aspects: Any) -> List[LambdalabsInstance]:
        """
            List the instances.

            :param aspects: Behaviour control (unused).

            :returns: The instance list.
        """
        rtnval = list(self._instances.values())
        return rtnval

    def get_instance(self, *, instance_id: str,
                     aspects: Any) -> LambdalabsInstance:
        """
            Retrieve an instance by id.

            :param instance_id: The instance id.
            :param aspects: Behaviour control (unused).

            :returns: The instance record.
        """
        rtnval = self._instances[instance_id]
        return rtnval

    def launch_instances(self, *, spec: Any,
                         aspects: Any) -> List[LambdalabsInstance]:
        """
            Launch instances from a launch spec.

            :param spec: The :class:`LambdalabsLaunchSpec`.
            :param aspects: Behaviour control (unused).

            :returns: The launched instance list.
        """
        self.launch_calls = self.launch_calls + 1
        launched: List[LambdalabsInstance] = []
        for _ in range(spec.quantity):
            instance_id = self._next_id(prefix="i")
            instance = LambdalabsInstance(
                identifier=instance_id, name=spec.name,
                status="active", region=spec.region_name,
                instance_type_name=spec.instance_type_name,
                ip="203.0.113.{}".format(self._counter),
                ssh_key_names=list(spec.ssh_key_names),
                file_system_names=list(spec.file_system_names),
            )
            self._instances[instance_id] = instance
            launched.append(instance)
        rtnval = launched
        return rtnval

    def terminate_instances(self, *, instance_ids: List[str],
                            aspects: Any) -> LambdalabsTerminationResult:
        """
            Terminate instances by id.

            :param instance_ids: The instance ids to terminate.
            :param aspects: Behaviour control (unused).

            :returns: A termination result.
        """
        self.terminate_calls = self.terminate_calls + 1
        terminated: List[LambdalabsInstance] = []
        already: List[str] = []
        for instance_id in instance_ids:
            if instance_id in self._instances:
                del self._instances[instance_id]
                terminated.append(LambdalabsInstance(
                    identifier=instance_id, name="terminated",
                    status="terminated", region="us-east-1",
                    instance_type_name="gpu_1x_h100_pcie",
                ))
            else:
                already.append(instance_id)
        rtnval = LambdalabsTerminationResult(terminated=terminated,
                                             already_terminated=already)
        return rtnval

    # -- clusters ------------------------------------------------------

    def list_clusters(self, *, aspects: Any) -> List[LambdalabsCluster]:
        """
            List the 1-click clusters.

            :param aspects: Behaviour control (unused).

            :returns: The cluster list.
        """
        rtnval = list(self._clusters.values())
        return rtnval

    def create_cluster(self, *, spec: Any, aspects: Any) -> LambdalabsCluster:
        """
            Create a 1-click cluster from a cluster spec.

            :param spec: The :class:`LambdalabsClusterSpec`.
            :param aspects: Behaviour control (unused).

            :returns: The created cluster record.
        """
        self.cluster_calls = self.cluster_calls + 1
        cluster_id = self._next_id(prefix="c")
        member_ids: List[str] = []
        for _ in range(spec.node_count):
            member_ids.append(self._next_id(prefix="i"))
        cluster = LambdalabsCluster(
            identifier=cluster_id, name=spec.name, status="active",
            region=spec.region_name,
            instance_type_name=spec.instance_type_name,
            instance_ids=member_ids,
        )
        self._clusters[cluster_id] = cluster
        rtnval = cluster
        return rtnval

    def delete_cluster(self, *, cluster_id: str, aspects: Any) -> None:
        """
            Delete a 1-click cluster by id (idempotent).

            :param cluster_id: The cluster id.
            :param aspects: Behaviour control (unused).

            :returns: ``None``.
        """
        if cluster_id in self._clusters:
            del self._clusters[cluster_id]
        return


class RecordingVpnControlPlane:
    """
        Minimal ``IVPNControlPlane`` test double recording the device ids
        passed to :meth:`delete_device`.
    """

    def __init__(self, *, minted_authkey: str = "tskey-mock-0001") -> None:
        """
            Construct a RecordingVpnControlPlane.

            :param minted_authkey: The auth key handed to the apply stage.
        """
        self.minted_authkey = minted_authkey
        self.deleted_device_ids: List[str] = []
        return

    def delete_device(self, *, device_id: str, aspects: Any) -> None:
        """
            Record a device-id de-registration.

            :param device_id: The device id to de-register.
            :param aspects: Behaviour control (unused).

            :returns: ``None``.
        """
        self.deleted_device_ids.append(device_id)
        return
