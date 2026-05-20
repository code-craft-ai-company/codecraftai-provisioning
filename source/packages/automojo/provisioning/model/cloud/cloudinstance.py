"""
    .. module:: cloudinstance
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Venue-neutral compute instance descriptor with HPC/AI slots.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional, Union

from automojo.restclient.base.schemaobject import SchemaObject
from automojo.restclient.base.schemafield import Field

from automojo.provisioning.model.exceptions import (
    SchemaValidationError, SchemaSemanticError
)
from automojo.provisioning.model.cloud.validators import validate_name
from automojo.provisioning.model.cloud.cloudimage import CloudImage
from automojo.provisioning.model.cloud.cloudacceleratorspec import (
    CloudAcceleratorSpec
)
from automojo.provisioning.model.cloud.cloudinterconnect import CloudInterconnect
from automojo.provisioning.model.cloud.sharedfsmountspec import SharedFsMountSpec
from automojo.provisioning.model.cloud.preemptionpolicy import PreemptionPolicy
from automojo.provisioning.model.vpn.vpnjoinspec import VPNJoinSpec


class CloudInstance(SchemaObject):
    """
        Venue-neutral compute instance descriptor.

        Carries everything any venue needs to bring up a single host, including
        optional accelerator, interconnect, shared-fs, VPN-join, and preemption
        policy slots.  Cross-resource validation (subnet exists, accelerator
        supported on venue) runs in the lifecycle validate stage.
    """

    name = Field(str, required=True)
    profile_ref = Field(str, required=True)
    image = Field(CloudImage, required=True)
    size = Field(str, required=True)
    subnet = Field(str, required=True)
    security_groups = Field(list, required=False, default=None)
    keypair = Field(str, required=False, default=None)
    user_data_script = Field(str, required=False, default=None)
    public_ip = Field(bool, required=False, default=False)
    tags = Field(list, required=False, default=None)
    vpn_join = Field(VPNJoinSpec, required=False, default=None)
    accelerators = Field(list, required=False, default=None)
    interconnect = Field(CloudInterconnect, required=False, default=None)
    placement_group = Field(str, required=False, default=None)
    shared_fs_mounts = Field(list, required=False, default=None)
    preemption_policy = Field(str, required=False,
                              default=PreemptionPolicy.FAIL.value)

    def __init__(self, *, name: str, profile_ref: str, image: CloudImage,
                 size: str, subnet: str,
                 security_groups: Optional[List[str]] = None,
                 keypair: Optional[str] = None,
                 user_data_script: Optional[str] = None,
                 public_ip: bool = False,
                 tags: Optional[List[Dict[str, str]]] = None,
                 vpn_join: Optional[VPNJoinSpec] = None,
                 accelerators: Optional[List[CloudAcceleratorSpec]] = None,
                 interconnect: Optional[CloudInterconnect] = None,
                 placement_group: Optional[str] = None,
                 shared_fs_mounts: Optional[List[SharedFsMountSpec]] = None,
                 preemption_policy: Union[PreemptionPolicy, str] =
                 PreemptionPolicy.FAIL) -> None:
        """
            Construct a CloudInstance.

            :param name: Instance name.
            :param profile_ref: Reference to a CloudResourceProfile name.
            :param image: CloudImage descriptor.
            :param size: Venue-neutral size identifier.
            :param subnet: Name of the parent CloudSubnet.
            :param security_groups: Optional list of CloudSecurityGroup names.
            :param keypair: Optional CloudKeyPair name.
            :param user_data_script: Optional raw user-data script.
            :param public_ip: Whether to attach a public IP.
            :param tags: Optional list of single-entry tag dicts.
            :param vpn_join: Optional VPNJoinSpec for control-plane VPN.
            :param accelerators: Optional list of CloudAcceleratorSpec.
            :param interconnect: Optional CloudInterconnect.
            :param placement_group: Optional placement group identifier.
            :param shared_fs_mounts: Optional list of SharedFsMountSpec.
            :param preemption_policy: PreemptionPolicy (default FAIL).

            :raises: SchemaValidationError, SchemaSemanticError
        """
        validate_name(value=name)
        validate_name(value=profile_ref)
        validate_name(value=subnet)

        if size is None or len(size) == 0:
            raise SchemaValidationError("size must not be empty.")

        if not isinstance(image, CloudImage):
            raise SchemaValidationError(
                "image must be a CloudImage instance."
            )

        effective_security_groups = security_groups if security_groups is not None else []
        effective_tags = tags if tags is not None else []
        effective_accelerators = accelerators if accelerators is not None else None
        effective_shared_fs_mounts = shared_fs_mounts if shared_fs_mounts is not None else None

        if isinstance(preemption_policy, PreemptionPolicy):
            policy_value = preemption_policy.value
        elif isinstance(preemption_policy, str):
            try:
                policy_value = PreemptionPolicy(preemption_policy).value
            except ValueError:
                raise SchemaValidationError(
                    "preemption_policy must be one of FAIL, REACQUIRE, "
                    "BEST_EFFORT, got {!r}".format(preemption_policy)
                ) from None
        else:
            raise SchemaValidationError(
                "preemption_policy must be a PreemptionPolicy or str."
            )

        if vpn_join is not None:
            if vpn_join.provider == "twingate" and not vpn_join.connector_only:
                raise SchemaSemanticError(
                    "Twingate vpn_join requires connector_only=True on the "
                    "owning instance; non-connector hosts must use Tailscale."
                )

        super().__init__(name=name, profile_ref=profile_ref, image=image,
                         size=size, subnet=subnet,
                         security_groups=effective_security_groups,
                         keypair=keypair, user_data_script=user_data_script,
                         public_ip=public_ip, tags=effective_tags,
                         vpn_join=vpn_join,
                         accelerators=effective_accelerators,
                         interconnect=interconnect,
                         placement_group=placement_group,
                         shared_fs_mounts=effective_shared_fs_mounts,
                         preemption_policy=policy_value)
        return

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CloudInstance":
        """
            Construct a CloudInstance from a serialised payload.

            Promotes nested image / vpn_join / accelerators / interconnect /
            shared_fs_mounts dicts to their typed classes.

            :param data: Serialised payload.

            :returns: A CloudInstance instance.
        """
        if not isinstance(data, dict):
            return data  # type: ignore

        image_payload = data["image"]
        if isinstance(image_payload, CloudImage):
            promoted_image = image_payload
        else:
            promoted_image = CloudImage.from_dict(image_payload)

        vpn_payload = data.get("vpn_join", None)
        promoted_vpn: Optional[VPNJoinSpec] = None
        if vpn_payload is not None:
            if isinstance(vpn_payload, VPNJoinSpec):
                promoted_vpn = vpn_payload
            else:
                promoted_vpn = VPNJoinSpec.from_dict(vpn_payload)

        accel_payload = data.get("accelerators", None)
        promoted_accels: Optional[List[CloudAcceleratorSpec]] = None
        if accel_payload is not None:
            promoted_accels = []
            for entry in accel_payload:
                if isinstance(entry, CloudAcceleratorSpec):
                    promoted_accels.append(entry)
                else:
                    promoted_accels.append(CloudAcceleratorSpec.from_dict(entry))

        ic_payload = data.get("interconnect", None)
        promoted_ic: Optional[CloudInterconnect] = None
        if ic_payload is not None:
            if isinstance(ic_payload, CloudInterconnect):
                promoted_ic = ic_payload
            else:
                promoted_ic = CloudInterconnect.from_dict(ic_payload)

        mounts_payload = data.get("shared_fs_mounts", None)
        promoted_mounts: Optional[List[SharedFsMountSpec]] = None
        if mounts_payload is not None:
            promoted_mounts = []
            for entry in mounts_payload:
                if isinstance(entry, SharedFsMountSpec):
                    promoted_mounts.append(entry)
                else:
                    promoted_mounts.append(SharedFsMountSpec.from_dict(entry))

        rtnval = cls(
            name=data["name"], profile_ref=data["profile_ref"],
            image=promoted_image, size=data["size"], subnet=data["subnet"],
            security_groups=data.get("security_groups", None),
            keypair=data.get("keypair", None),
            user_data_script=data.get("user_data_script", None),
            public_ip=data.get("public_ip", False),
            tags=data.get("tags", None),
            vpn_join=promoted_vpn,
            accelerators=promoted_accels,
            interconnect=promoted_ic,
            placement_group=data.get("placement_group", None),
            shared_fs_mounts=promoted_mounts,
            preemption_policy=data.get(
                "preemption_policy", PreemptionPolicy.FAIL.value
            ),
        )
        return rtnval
