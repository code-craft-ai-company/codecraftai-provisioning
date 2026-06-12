"""
    .. module:: _mockclient
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: MockNutanixClient — an in-memory stand-in for the Nutanix
               Prism Central interop client used by the venue test suite.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from ccai.restclient.nutanix.model.nutanixcategory import NutanixCategory
from ccai.restclient.nutanix.model.nutanixcluster import NutanixCluster
from ccai.restclient.nutanix.model.nutaniximage import NutanixImage
from ccai.restclient.nutanix.model.nutanixsecuritypolicy import (
    NutanixSecurityPolicy
)
from ccai.restclient.nutanix.model.nutanixsubnet import NutanixSubnet
from ccai.restclient.nutanix.model.nutanixtaskstatus import NutanixTaskStatus
from ccai.restclient.nutanix.model.nutanixvm import NutanixVm
from ccai.restclient.nutanix.model.nutanixvolumegroup import (
    NutanixVolumeGroup
)
from ccai.restclient.nutanix.model.nutanixvpc import NutanixVpc


class _MockTaskHandle:
    """
        In-memory stand-in for :class:`NutanixTaskHandle`.

        Carries an immediately-terminal task referencing one entity uuid,
        so the venue apply stages observe a deterministic, fast-completing
        task without driving a real poll loop.
    """

    def __init__(self, *, task_uuid: str,
                 entity_uuid: Optional[str]) -> None:
        """
            Construct a _MockTaskHandle.

            :param task_uuid: The task uuid.
            :param entity_uuid: The entity uuid the task acted upon.
        """
        self._task_uuid = task_uuid
        self._entity_uuid = entity_uuid
        return

    def task_id(self) -> str:
        """
            Return the task uuid.

            :returns: The task uuid string.
        """
        rtnval = self._task_uuid
        return rtnval

    def wait(self, *, aspects: Any) -> None:
        """
            Return immediately — the mock task is already terminal.

            :param aspects: Behaviour control (unused).

            :returns: ``None``.
        """
        return

    def result_entity_uuid(self, *, aspects: Any) -> Optional[str]:
        """
            Return the entity uuid the task acted upon.

            :param aspects: Behaviour control (unused).

            :returns: The entity uuid, or ``None``.
        """
        rtnval = self._entity_uuid
        return rtnval


class _MockClustersGroup:
    """
        In-memory stand-in for the interop ``ClustersGroup``.
    """

    def __init__(self, *, owner: "MockNutanixClient") -> None:
        """
            Construct a _MockClustersGroup.

            :param owner: The owning :class:`MockNutanixClient`.
        """
        self._owner = owner
        return

    def list(self, *, aspects: Any) -> List[NutanixCluster]:
        """
            List the Prism clusters.

            :param aspects: Behaviour control (unused).

            :returns: The cluster list.
        """
        rtnval = list(self._owner.clusters_state.values())
        return rtnval


class _MockImagesGroup:
    """
        In-memory stand-in for the interop ``ImagesGroup``.
    """

    def __init__(self, *, owner: "MockNutanixClient") -> None:
        """
            Construct a _MockImagesGroup.

            :param owner: The owning :class:`MockNutanixClient`.
        """
        self._owner = owner
        return

    def list(self, *, aspects: Any) -> List[NutanixImage]:
        """
            List the registered images.

            :param aspects: Behaviour control (unused).

            :returns: The image list.
        """
        rtnval = list(self._owner.images_state.values())
        return rtnval

    def find_by_name(self, *, name: str,
                     aspects: Any) -> Optional[NutanixImage]:
        """
            Return the image with the given name, or ``None``.

            :param name: The image name to match.
            :param aspects: Behaviour control (unused).

            :returns: A :class:`NutanixImage` or ``None``.
        """
        rtnval = self._owner.images_state.get(name, None)
        return rtnval


class _MockVpcsGroup:
    """
        In-memory stand-in for the interop ``VpcsGroup``.
    """

    def __init__(self, *, owner: "MockNutanixClient") -> None:
        """
            Construct a _MockVpcsGroup.

            :param owner: The owning :class:`MockNutanixClient`.
        """
        self._owner = owner
        return

    def list(self, *, aspects: Any) -> List[NutanixVpc]:
        """
            List the Flow VPCs.

            :param aspects: Behaviour control (unused).

            :returns: The VPC list.
        """
        rtnval = list(self._owner.vpcs_state.values())
        return rtnval

    def find_by_name(self, *, name: str,
                     aspects: Any) -> Optional[NutanixVpc]:
        """
            Return the VPC with the given name, or ``None``.

            :param name: The VPC name.
            :param aspects: Behaviour control (unused).

            :returns: A :class:`NutanixVpc` or ``None``.
        """
        rtnval = self._owner.vpcs_state.get(name, None)
        return rtnval

    def create(self, *, spec: Any, aspects: Any) -> _MockTaskHandle:
        """
            Create a VPC from a spec, idempotently by name.

            :param spec: The :class:`VpcSpec`.
            :param aspects: Behaviour control (unused).

            :returns: A :class:`_MockTaskHandle`.
        """
        existing = self._owner.vpcs_state.get(spec.name, None)
        if existing is not None:
            rtnval = _MockTaskHandle(task_uuid=existing.uuid,
                                     entity_uuid=existing.uuid)
            return rtnval
        self._owner.create_vpc_calls = self._owner.create_vpc_calls + 1
        uuid = self._owner.next_id(prefix="vpc")
        record = NutanixVpc(uuid=uuid, name=spec.name,
                            raw={"metadata": {"uuid": uuid},
                                 "spec": {"name": spec.name}})
        self._owner.vpcs_state[spec.name] = record
        rtnval = _MockTaskHandle(task_uuid=uuid, entity_uuid=uuid)
        return rtnval

    def delete(self, *, vpc_uuid: str, aspects: Any) -> None:
        """
            Delete a VPC by uuid (idempotent).

            :param vpc_uuid: The VPC uuid.
            :param aspects: Behaviour control (unused).

            :returns: ``None``.
        """
        for name, record in list(self._owner.vpcs_state.items()):
            if record.uuid == vpc_uuid:
                del self._owner.vpcs_state[name]
        return


class _MockSubnetsGroup:
    """
        In-memory stand-in for the interop ``SubnetsGroup``.
    """

    def __init__(self, *, owner: "MockNutanixClient") -> None:
        """
            Construct a _MockSubnetsGroup.

            :param owner: The owning :class:`MockNutanixClient`.
        """
        self._owner = owner
        return

    def list(self, *, aspects: Any) -> List[NutanixSubnet]:
        """
            List the Prism subnets.

            :param aspects: Behaviour control (unused).

            :returns: The subnet list.
        """
        rtnval = list(self._owner.subnets_state.values())
        return rtnval

    def find_by_name(self, *, name: str,
                     aspects: Any) -> Optional[NutanixSubnet]:
        """
            Return the subnet with the given name, or ``None``.

            :param name: The subnet name.
            :param aspects: Behaviour control (unused).

            :returns: A :class:`NutanixSubnet` or ``None``.
        """
        rtnval = self._owner.subnets_state.get(name, None)
        return rtnval

    def create(self, *, spec: Any, aspects: Any) -> _MockTaskHandle:
        """
            Create a subnet from a spec, idempotently by name.

            :param spec: The :class:`SubnetSpec`.
            :param aspects: Behaviour control (unused).

            :returns: A :class:`_MockTaskHandle`.
        """
        existing = self._owner.subnets_state.get(spec.name, None)
        if existing is not None:
            rtnval = _MockTaskHandle(task_uuid=existing.uuid,
                                     entity_uuid=existing.uuid)
            return rtnval
        self._owner.create_subnet_calls = (
            self._owner.create_subnet_calls + 1
        )
        uuid = self._owner.next_id(prefix="subnet")
        record = NutanixSubnet(uuid=uuid, name=spec.name,
                               subnet_type=spec.subnet_type,
                               vlan_id=spec.vlan_id,
                               cluster_uuid=spec.cluster_uuid,
                               raw={"metadata": {"uuid": uuid},
                                    "spec": {"name": spec.name}})
        self._owner.subnets_state[spec.name] = record
        rtnval = _MockTaskHandle(task_uuid=uuid, entity_uuid=uuid)
        return rtnval

    def delete(self, *, subnet_uuid: str, aspects: Any) -> None:
        """
            Delete a subnet by uuid (idempotent).

            :param subnet_uuid: The subnet uuid.
            :param aspects: Behaviour control (unused).

            :returns: ``None``.
        """
        for name, record in list(self._owner.subnets_state.items()):
            if record.uuid == subnet_uuid:
                del self._owner.subnets_state[name]
        return


class _MockSecurityPoliciesGroup:
    """
        In-memory stand-in for the interop ``SecurityPoliciesGroup``.
    """

    def __init__(self, *, owner: "MockNutanixClient") -> None:
        """
            Construct a _MockSecurityPoliciesGroup.

            :param owner: The owning :class:`MockNutanixClient`.
        """
        self._owner = owner
        return

    def list(self, *, aspects: Any) -> List[NutanixSecurityPolicy]:
        """
            List the Flow security policies.

            :param aspects: Behaviour control (unused).

            :returns: The security-policy list.
        """
        rtnval = list(self._owner.policies_state.values())
        return rtnval

    def find_by_name(self, *, name: str,
                     aspects: Any) -> Optional[NutanixSecurityPolicy]:
        """
            Return the security policy with the given name, or ``None``.

            :param name: The policy name.
            :param aspects: Behaviour control (unused).

            :returns: A :class:`NutanixSecurityPolicy` or ``None``.
        """
        rtnval = self._owner.policies_state.get(name, None)
        return rtnval

    def create(self, *, spec: Any, aspects: Any) -> _MockTaskHandle:
        """
            Create a security policy from a spec, idempotently by name.

            :param spec: The :class:`SecurityPolicySpec`.
            :param aspects: Behaviour control (unused).

            :returns: A :class:`_MockTaskHandle`.
        """
        existing = self._owner.policies_state.get(spec.name, None)
        if existing is not None:
            rtnval = _MockTaskHandle(task_uuid=existing.uuid,
                                     entity_uuid=existing.uuid)
            return rtnval
        self._owner.create_policy_calls = (
            self._owner.create_policy_calls + 1
        )
        uuid = self._owner.next_id(prefix="policy")
        record = NutanixSecurityPolicy(
            uuid=uuid, name=spec.name, raw={"metadata": {"uuid": uuid}}
        )
        self._owner.policies_state[spec.name] = record
        rtnval = _MockTaskHandle(task_uuid=uuid, entity_uuid=uuid)
        return rtnval

    def delete(self, *, policy_uuid: str, aspects: Any) -> None:
        """
            Delete a security policy by uuid (idempotent).

            :param policy_uuid: The policy uuid.
            :param aspects: Behaviour control (unused).

            :returns: ``None``.
        """
        for name, record in list(self._owner.policies_state.items()):
            if record.uuid == policy_uuid:
                del self._owner.policies_state[name]
        return


class _MockVolumeGroupsGroup:
    """
        In-memory stand-in for the interop ``VolumeGroupsGroup``.
    """

    def __init__(self, *, owner: "MockNutanixClient") -> None:
        """
            Construct a _MockVolumeGroupsGroup.

            :param owner: The owning :class:`MockNutanixClient`.
        """
        self._owner = owner
        return

    def list(self, *, aspects: Any) -> List[NutanixVolumeGroup]:
        """
            List the volume groups.

            :param aspects: Behaviour control (unused).

            :returns: The volume-group list.
        """
        rtnval = list(self._owner.volume_groups_state.values())
        return rtnval

    def find_by_name(self, *, name: str,
                     aspects: Any) -> Optional[NutanixVolumeGroup]:
        """
            Return the volume group with the given name, or ``None``.

            :param name: The volume-group name.
            :param aspects: Behaviour control (unused).

            :returns: A :class:`NutanixVolumeGroup` or ``None``.
        """
        rtnval = self._owner.volume_groups_state.get(name, None)
        return rtnval

    def create(self, *, spec: Any, aspects: Any) -> _MockTaskHandle:
        """
            Create a volume group from a spec, idempotently by name.

            :param spec: The :class:`VolumeGroupSpec`.
            :param aspects: Behaviour control (unused).

            :returns: A :class:`_MockTaskHandle`.
        """
        existing = self._owner.volume_groups_state.get(spec.name, None)
        if existing is not None:
            rtnval = _MockTaskHandle(task_uuid=existing.uuid,
                                     entity_uuid=existing.uuid)
            return rtnval
        self._owner.create_volume_group_calls = (
            self._owner.create_volume_group_calls + 1
        )
        uuid = self._owner.next_id(prefix="vg")
        record = NutanixVolumeGroup(
            uuid=uuid, name=spec.name,
            raw={"metadata": {"uuid": uuid}}
        )
        self._owner.volume_groups_state[spec.name] = record
        rtnval = _MockTaskHandle(task_uuid=uuid, entity_uuid=uuid)
        return rtnval

    def delete(self, *, volume_group_uuid: str, aspects: Any) -> None:
        """
            Delete a volume group by uuid (idempotent).

            :param volume_group_uuid: The volume-group uuid.
            :param aspects: Behaviour control (unused).

            :returns: ``None``.
        """
        state = self._owner.volume_groups_state
        for name, record in list(state.items()):
            if record.uuid == volume_group_uuid:
                del state[name]
        return


class _MockVmsGroup:
    """
        In-memory stand-in for the interop ``VmsGroup``.
    """

    def __init__(self, *, owner: "MockNutanixClient") -> None:
        """
            Construct a _MockVmsGroup.

            :param owner: The owning :class:`MockNutanixClient`.
        """
        self._owner = owner
        return

    def list(self, *, aspects: Any) -> List[NutanixVm]:
        """
            List the Prism VMs.

            :param aspects: Behaviour control (unused).

            :returns: The VM list.
        """
        rtnval = list(self._owner.vms_state.values())
        return rtnval

    def find_by_name(self, *, name: str,
                     aspects: Any) -> Optional[NutanixVm]:
        """
            Return the VM with the given name, or ``None``.

            :param name: The VM name.
            :param aspects: Behaviour control (unused).

            :returns: A :class:`NutanixVm` or ``None``.
        """
        rtnval = self._owner.vms_state.get(name, None)
        return rtnval

    def create(self, *, spec: Any, aspects: Any) -> _MockTaskHandle:
        """
            Create a VM from a spec, idempotently by name.

            :param spec: The :class:`VmSpec`.
            :param aspects: Behaviour control (unused).

            :returns: A :class:`_MockTaskHandle`.
        """
        existing = self._owner.vms_state.get(spec.name, None)
        if existing is not None:
            rtnval = _MockTaskHandle(task_uuid=existing.uuid,
                                     entity_uuid=existing.uuid)
            return rtnval
        self._owner.create_vm_calls = self._owner.create_vm_calls + 1
        uuid = self._owner.next_id(prefix="vm")

        categories_mapping: Dict[str, List[str]] = {}
        for key, value in spec.categories.items():
            categories_mapping[key] = [value]

        payload = spec.to_payload()
        raw = {
            "metadata": {"uuid": uuid,
                         "categories_mapping": categories_mapping},
            "spec": payload.get("spec", {}),
            "status": {"name": spec.name},
        }
        record = NutanixVm(uuid=uuid, name=spec.name, spec_version=1,
                           power_state=spec.power_state,
                           num_vcpus=spec.num_vcpus,
                           memory_mib=spec.memory_mib,
                           cluster_uuid=spec.cluster_uuid,
                           ip_addresses=["10.20.0.50"], raw=raw)
        self._owner.vms_state[spec.name] = record
        self._owner.vm_user_data[spec.name] = spec.cloud_init_user_data
        rtnval = _MockTaskHandle(task_uuid=uuid, entity_uuid=uuid)
        return rtnval

    def update(self, *, vm_uuid: str, spec: Any,
               aspects: Any) -> _MockTaskHandle:
        """
            Replace a VM's intent spec in place (vCPU / memory resize).

            :param vm_uuid: The VM uuid.
            :param spec: The :class:`VmSpec` replacement.
            :param aspects: Behaviour control (unused).

            :returns: A :class:`_MockTaskHandle`.
        """
        _ = aspects
        for record in self._owner.vms_state.values():
            if record.uuid == vm_uuid:
                self._owner.update_vm_calls = (
                    self._owner.update_vm_calls + 1
                )
                record.num_vcpus = spec.num_vcpus
                record.memory_mib = spec.memory_mib
        rtnval = _MockTaskHandle(task_uuid=vm_uuid, entity_uuid=vm_uuid)
        return rtnval

    def power_on(self, *, vm_uuid: str, aspects: Any) -> _MockTaskHandle:
        """
            Power a VM on (idempotent).

            :param vm_uuid: The VM uuid.
            :param aspects: Behaviour control (unused).

            :returns: A :class:`_MockTaskHandle`.
        """
        for record in self._owner.vms_state.values():
            if record.uuid == vm_uuid:
                record.power_state = "ON"
        rtnval = _MockTaskHandle(task_uuid=vm_uuid, entity_uuid=vm_uuid)
        return rtnval

    def power_off(self, *, vm_uuid: str, aspects: Any) -> _MockTaskHandle:
        """
            Power a VM off (idempotent).

            :param vm_uuid: The VM uuid.
            :param aspects: Behaviour control (unused).

            :returns: A :class:`_MockTaskHandle`.
        """
        for record in self._owner.vms_state.values():
            if record.uuid == vm_uuid:
                record.power_state = "OFF"
        rtnval = _MockTaskHandle(task_uuid=vm_uuid, entity_uuid=vm_uuid)
        return rtnval

    def delete(self, *, vm_uuid: str, aspects: Any) -> None:
        """
            Delete a VM by uuid (idempotent).

            :param vm_uuid: The VM uuid.
            :param aspects: Behaviour control (unused).

            :returns: ``None``.
        """
        for name, record in list(self._owner.vms_state.items()):
            if record.uuid == vm_uuid:
                del self._owner.vms_state[name]
        return


class _MockCategoriesGroup:
    """
        In-memory stand-in for the interop ``CategoriesGroup``.
    """

    def __init__(self, *, owner: "MockNutanixClient") -> None:
        """
            Construct a _MockCategoriesGroup.

            :param owner: The owning :class:`MockNutanixClient`.
        """
        self._owner = owner
        return

    def ensure_category(self, *, name: str, value: str,
                        aspects: Any) -> NutanixCategory:
        """
            Ensure a category key/value pair exists (idempotent).

            :param name: The category key.
            :param value: The category value.
            :param aspects: Behaviour control (unused).

            :returns: A :class:`NutanixCategory`.
        """
        bucket = self._owner.categories_state.setdefault(name, set())
        bucket.add(value)
        rtnval = NutanixCategory(key=name, value=value,
                                 raw={"name": name, "value": value})
        return rtnval


class _MockTasksGroup:
    """
        In-memory stand-in for the interop ``TasksGroup``.

        Tasks are keyed in :attr:`MockNutanixClient.tasks_state`; an
        unknown uuid is reported as ``RUNNING`` so a real
        :class:`NutanixTaskHandle` constructed against this group keeps
        polling — used by the timeout-aspect test.
    """

    def __init__(self, *, owner: "MockNutanixClient") -> None:
        """
            Construct a _MockTasksGroup.

            :param owner: The owning :class:`MockNutanixClient`.
        """
        self._owner = owner
        return

    def get(self, *, task_uuid: str, aspects: Any) -> NutanixTaskStatus:
        """
            Return the status of a task.

            :param task_uuid: The task uuid.
            :param aspects: Behaviour control (unused).

            :returns: A :class:`NutanixTaskStatus`.
        """
        state = self._owner.tasks_state.get(task_uuid, "RUNNING")
        payload: Dict[str, Any] = {"uuid": task_uuid, "status": state,
                                   "percentage_complete": 100}
        rtnval = NutanixTaskStatus.from_dict(payload)
        return rtnval


class MockNutanixClient:
    """
        In-memory stand-in for :class:`NutanixClient`.

        Holds deterministic dictionaries for clusters, images, VPCs,
        subnets, security policies, volume groups, VMs and categories so
        the venue provisioner can be exercised without any Prism Central
        REST traffic.  Mutating calls update the in-memory state so
        apply / destroy idempotence can be observed.  The api groups are
        reachable through the same public attributes as the real client.
    """

    def __init__(self) -> None:
        """
            Construct an empty MockNutanixClient seeded with one cluster
            and the default Ubuntu image.
        """
        self.clusters_state: Dict[str, NutanixCluster] = {}
        self.images_state: Dict[str, NutanixImage] = {}
        self.vpcs_state: Dict[str, NutanixVpc] = {}
        self.subnets_state: Dict[str, NutanixSubnet] = {}
        self.policies_state: Dict[str, NutanixSecurityPolicy] = {}
        self.volume_groups_state: Dict[str, NutanixVolumeGroup] = {}
        self.vms_state: Dict[str, NutanixVm] = {}
        self.categories_state: Dict[str, set] = {}
        self.tasks_state: Dict[str, str] = {}
        self.vm_user_data: Dict[str, Any] = {}

        self._counter = 0
        self.create_vpc_calls = 0
        self.create_subnet_calls = 0
        self.create_policy_calls = 0
        self.create_volume_group_calls = 0
        self.create_vm_calls = 0
        self.update_vm_calls = 0

        self.clusters = _MockClustersGroup(owner=self)
        self.images = _MockImagesGroup(owner=self)
        self.vpcs = _MockVpcsGroup(owner=self)
        self.subnets = _MockSubnetsGroup(owner=self)
        self.security_policies = _MockSecurityPoliciesGroup(owner=self)
        self.volume_groups = _MockVolumeGroupsGroup(owner=self)
        self.vms = _MockVmsGroup(owner=self)
        self.categories = _MockCategoriesGroup(owner=self)
        self.tasks = _MockTasksGroup(owner=self)

        self.seed_cluster(name="homelab-cluster")
        self.seed_image(name="ubuntu-24.04-server-cloudimg-amd64")
        return

    def next_id(self, *, prefix: str) -> str:
        """
            Allocate a deterministic identifier.

            :param prefix: The identifier prefix.

            :returns: A new identifier string.
        """
        self._counter = self._counter + 1
        rtnval = "{}-{:08d}".format(prefix, self._counter)
        return rtnval

    def seed_cluster(self, *, name: str) -> str:
        """
            Seed a Prism cluster into the mock state.

            :param name: The cluster name.

            :returns: The seeded cluster uuid.
        """
        uuid = self.next_id(prefix="cluster")
        self.clusters_state[uuid] = NutanixCluster(
            uuid=uuid, name=name,
            raw={"metadata": {"uuid": uuid}, "status": {"name": name}},
        )
        rtnval = uuid
        return rtnval

    def seed_image(self, *, name: str) -> str:
        """
            Seed a registered Prism image into the mock state.

            :param name: The image name.

            :returns: The seeded image uuid.
        """
        uuid = self.next_id(prefix="image")
        self.images_state[name] = NutanixImage(
            uuid=uuid, name=name, image_type="DISK_IMAGE",
            raw={"metadata": {"uuid": uuid}},
        )
        rtnval = uuid
        return rtnval


class RecordingVpnControlPlane:
    """
        Minimal ``IVPNControlPlane`` test double recording the device ids
        passed to :meth:`delete_device`.
    """

    def __init__(self, *, minted_authkey: str = "tskey-mock-0001") -> None:
        """
            Construct a RecordingVpnControlPlane.

            :param minted_authkey: The auth key handed to the apply
                stage.
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
