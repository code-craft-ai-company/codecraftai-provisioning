"""
    .. module:: instancemanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: AWS EC2 Instance manager — user-data, EFA, accelerator SKU, preemption.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import base64
import os

from typing import Any, Dict, List, Optional, Tuple

import yaml

from automojo.provisioning.cloudinit.vpncloudinitrenderer import (
    render_cloud_init
)
from automojo.provisioning.model.cloud.cloudacceleratorcatalog import (
    CloudAcceleratorCatalog
)
from automojo.provisioning.model.cloud.cloudinstance import CloudInstance
from automojo.provisioning.model.cloud.preemptionpolicy import PreemptionPolicy
from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.venues.aws.awsboto3sessionfactory import (
    AwsBoto3SessionFactory
)
from automojo.provisioning.venues.aws.awserrors import AwsValidationError
from automojo.provisioning.venues.aws.awsidempotency import (
    owner_filters, tag_dict_from_aws
)
from automojo.provisioning.venues.aws.awstagging import (
    base_resource_tags, tag_specifications, from_aws, RESOURCE_NAME_TAG_KEY
)
from automojo.provisioning.venues.aws.resources.imageresolver import (
    ImageResolver
)
from automojo.provisioning.venues.aws.resources.placementgroupmanager import (
    PlacementGroupManager
)


# AWS instance families that support EFA.
_EFA_CAPABLE_FAMILIES = frozenset({
    "p4d", "p4de", "p5", "p5e", "p6",
    "c5n", "c6gn", "c6in", "c7gn",
    "hpc6a", "hpc7a", "hpc7g",
    "trn1", "trn1n",
})


def _instance_family(*, instance_type: str) -> str:
    """
        Return the family prefix from an AWS instance type.

        :param instance_type: e.g. ``p5.48xlarge``.

        :returns: Family prefix (e.g. ``p5``).
    """
    if "." not in instance_type:
        rtnval = instance_type
        return rtnval
    rtnval = instance_type.split(".", 1)[0]
    return rtnval


def is_efa_capable(*, instance_type: str) -> bool:
    """
        Return True when the instance family supports EFA.

        :param instance_type: AWS instance type string.

        :returns: True when EFA-capable.
    """
    family = _instance_family(instance_type=instance_type)
    rtnval = family in _EFA_CAPABLE_FAMILIES
    return rtnval


class InstanceManager:
    """
        Manager for EC2 Instances.

        Wires together:

        - cloud-init render via :func:`render_cloud_init`,
        - GPU SKU resolution via :class:`CloudAcceleratorCatalog`,
        - cluster placement group attachment when interconnect=EFA,
        - preemption-policy → on-demand vs spot,
        - tag-based read-before-create for idempotence.
    """

    KIND: str = "instance"
    VENUE_NAME: str = "aws"

    def __init__(self, *, session_factory: AwsBoto3SessionFactory,
                 image_resolver: ImageResolver,
                 placement_manager: PlacementGroupManager,
                 catalog: CloudAcceleratorCatalog) -> None:
        """
            Construct an InstanceManager.

            :param session_factory: AwsBoto3SessionFactory.
            :param image_resolver: ImageResolver.
            :param placement_manager: PlacementGroupManager.
            :param catalog: CloudAcceleratorCatalog (for GPU SKU lookup).
        """
        self._session_factory: AwsBoto3SessionFactory = session_factory
        self._image_resolver: ImageResolver = image_resolver
        self._placement_manager: PlacementGroupManager = placement_manager
        self._catalog: CloudAcceleratorCatalog = catalog
        return

    def _ec2(self) -> Any:
        rtnval = self._session_factory.client(service_name="ec2")
        return rtnval

    def resolve_instance_type(self, *, instance: CloudInstance) -> str:
        """
            Resolve the AWS instance type to launch.

            Strategy:

            - When ``accelerators`` is set, consult the accelerator catalog
              with the first accelerator's neutral model name.  If the user
              also provided ``size``, the two must agree.
            - Otherwise return ``instance.size`` verbatim.

            :param instance: The neutral CloudInstance.

            :returns: AWS instance-type string.
            :raises: AwsValidationError
        """
        accelerators = instance.accelerators if instance.accelerators is not None else []
        if len(accelerators) == 0:
            rtnval = instance.size
            return rtnval

        first = accelerators[0]
        try:
            sku = self._catalog.resolve(neutral_name=first.model,
                                        venue=self.VENUE_NAME)
        except Exception as xcpt:
            err_msg_lines = [
                "AWS instance accelerator could not be resolved by the catalog."
            ]
            err_msg_lines.append("INSTANCE: {}".format(instance.name))
            err_msg_lines.append("MODEL: {}".format(first.model))
            err_msg_lines.append("CAUSE: {}".format(xcpt))
            err_msg = os.linesep.join(err_msg_lines)
            raise AwsValidationError(err_msg) from None

        if instance.size is not None and len(instance.size) > 0:
            if instance.size != sku and instance.size != first.model:
                err_msg_lines = [
                    "Instance.size conflicts with accelerator-resolved SKU."
                ]
                err_msg_lines.append("INSTANCE: {}".format(instance.name))
                err_msg_lines.append("REQUESTED_SIZE: {}".format(instance.size))
                err_msg_lines.append("RESOLVED_SKU: {}".format(sku))
                err_msg = os.linesep.join(err_msg_lines)
                raise AwsValidationError(err_msg)

        rtnval = sku
        return rtnval

    def render_user_data(self, *, instance: CloudInstance,
                         authkey: str) -> str:
        """
            Render the cloud-init body (yaml) for the instance.

            :param instance: The CloudInstance.
            :param authkey: Minted auth-key value.

            :returns: A yaml-formatted ``#cloud-config`` body, or "" when
                      no ``vpn_join`` is declared.
        """
        if instance.vpn_join is None:
            base_script = instance.user_data_script
            rtnval = base_script if base_script is not None else ""
            return rtnval

        rendered_hostname = instance.vpn_join.hostname_template.replace(
            "{instance_name}", instance.name
        )
        cloud_init = render_cloud_init(
            spec=instance.vpn_join,
            authkey=authkey,
            rendered_hostname=rendered_hostname,
            image_family=instance.image.family,
        )

        body_lines: List[str] = ["#cloud-config"]
        body_lines.append(yaml.safe_dump(cloud_init, sort_keys=False))
        rtnval = "\n".join(body_lines)
        return rtnval

    def find(self, *, run_id: str, name: str) -> Optional[Dict[str, Any]]:
        """
            Find an existing owned instance by run+name tags.

            :param run_id: Run identifier.
            :param name: Neutral instance name.

            :returns: An instance dict or None.
        """
        client = self._ec2()
        filters = owner_filters(run_id=run_id, resource_name=name)
        filters.append({"Name": "instance-state-name",
                        "Values": ["pending", "running", "stopping",
                                   "stopped"]})
        response = client.describe_instances(Filters=filters)
        for reservation in response.get("Reservations", []):
            instances = reservation.get("Instances", [])
            if len(instances) > 0:
                rtnval: Optional[Dict[str, Any]] = instances[0]
                return rtnval
        rtnval = None
        return rtnval

    def ensure(self, *, desired: CloudInstance, run_id: str,
               subnet_id: str, sg_ids: List[str],
               keypair_aws_name: Optional[str],
               default_tags: List[Dict[str, str]],
               authkey: Optional[str],
               aspects: Any
               ) -> Tuple[ProvisionedResource, Dict[str, Any]]:
        """
            Match-then-act create-or-reuse for an EC2 instance.

            :param desired: Desired CloudInstance.
            :param run_id: Run identifier.
            :param subnet_id: Resolved subnet id for the instance.
            :param sg_ids: Resolved security group ids.
            :param keypair_aws_name: AWS-side key pair name or None.
            :param default_tags: Venue default tags.
            :param authkey: Pre-minted VPN authkey (when vpn_join is set).
            :param aspects: Aspects.

            :returns: (ProvisionedResource, info-dict including ``vpn_device_id``).
        """
        client = self._ec2()
        existing = self.find(run_id=run_id, name=desired.name)

        info: Dict[str, Any] = {}

        if existing is not None:
            attributes = self._instance_attributes(existing=existing)
            rtnval_resource = ProvisionedResource(
                kind=self.KIND, name=desired.name,
                venue_id=existing.get("InstanceId", ""),
                attributes=attributes,
                tags=from_aws(aws_tags=existing.get("Tags", [])),
            )
            info["vpn_device_id"] = self._vpn_device_id_from_tags(
                existing=existing
            )
            rtnval = (rtnval_resource, info)
            return rtnval

        instance_type = self.resolve_instance_type(instance=desired)
        ami_id = self._image_resolver.resolve(image=desired.image)

        user_data_body = self.render_user_data(
            instance=desired,
            authkey=authkey if authkey is not None else "PLACEHOLDER",
        )
        user_data_b64 = ""
        if len(user_data_body) > 0:
            user_data_b64 = base64.b64encode(
                user_data_body.encode("utf-8")
            ).decode("utf-8")

        neutral_tags = base_resource_tags(
            run_id=run_id, resource_name=desired.name,
            resource_kind=self.KIND, extra=list(desired.tags),
            defaults=default_tags,
        )

        # Inject a vpn-device-id placeholder tag so destroy can find it
        # later if the control plane reports an id back to the caller.
        tag_specs = tag_specifications(
            resource_type="instance", neutral_tags=neutral_tags
        )

        run_kwargs: Dict[str, Any] = {}
        run_kwargs["ImageId"] = ami_id
        run_kwargs["InstanceType"] = instance_type
        run_kwargs["MinCount"] = 1
        run_kwargs["MaxCount"] = 1
        run_kwargs["SubnetId"] = subnet_id
        if len(sg_ids) > 0:
            run_kwargs["SecurityGroupIds"] = list(sg_ids)
        if keypair_aws_name is not None and len(keypair_aws_name) > 0:
            run_kwargs["KeyName"] = keypair_aws_name
        if len(user_data_b64) > 0:
            run_kwargs["UserData"] = user_data_b64
        run_kwargs["TagSpecifications"] = tag_specs

        # Placement group + EFA when interconnect=EFA.
        if desired.interconnect is not None and desired.interconnect.kind == "EFA":
            if not is_efa_capable(instance_type=instance_type):
                err_msg_lines = [
                    "EFA requested but instance family does not support EFA."
                ]
                err_msg_lines.append("INSTANCE: {}".format(desired.name))
                err_msg_lines.append("INSTANCE_TYPE: {}".format(instance_type))
                err_msg = os.linesep.join(err_msg_lines)
                raise AwsValidationError(err_msg)
            pg_logical = desired.placement_group if desired.placement_group is not None else "{}-pg".format(desired.name)
            pg_name = self._placement_manager.ensure(
                run_id=run_id, logical_name=pg_logical,
                default_tags=default_tags, aspects=aspects,
            )
            run_kwargs["Placement"] = {"GroupName": pg_name}
            # EFA-enabled primary ENI.
            run_kwargs.pop("SubnetId", None)
            run_kwargs.pop("SecurityGroupIds", None)
            run_kwargs["NetworkInterfaces"] = [{
                "DeviceIndex": 0,
                "SubnetId": subnet_id,
                "Groups": list(sg_ids),
                "InterfaceType": "efa",
                "AssociatePublicIpAddress": bool(desired.public_ip),
            }]

        # Preemption policy mapping.
        policy = desired.preemption_policy
        if isinstance(policy, PreemptionPolicy):
            policy_value = policy.value
        else:
            policy_value = str(policy)

        if policy_value in ("REACQUIRE", "BEST_EFFORT"):
            run_kwargs["InstanceMarketOptions"] = {
                "MarketType": "spot",
                "SpotOptions": {"SpotInstanceType": "one-time"},
            }

        response = client.run_instances(**run_kwargs)
        instances = response.get("Instances", [])
        created = instances[0] if len(instances) > 0 else {}
        instance_id = created.get("InstanceId", "")

        # Refresh the instance entry (moto returns the launch shape directly).
        refresh = client.describe_instances(InstanceIds=[instance_id])
        for reservation in refresh.get("Reservations", []):
            for entry in reservation.get("Instances", []):
                created = entry

        attributes = self._instance_attributes(existing=created)
        attributes["instance_type"] = instance_type
        attributes["ami_id"] = ami_id
        attributes["preemption_policy"] = policy_value
        if len(user_data_body) > 0:
            attributes["user_data_present"] = True

        rtnval_resource = ProvisionedResource(
            kind=self.KIND, name=desired.name,
            venue_id=instance_id, attributes=attributes,
            tags=from_aws(aws_tags=created.get("Tags", [])),
        )
        info["vpn_device_id"] = None
        info["user_data_body"] = user_data_body
        rtnval = (rtnval_resource, info)
        return rtnval

    def _instance_attributes(self, *, existing: Dict[str, Any]
                             ) -> Dict[str, Any]:
        """
            Build the attributes dict for a ProvisionedResource.

            :param existing: AWS describe-instances entry.

            :returns: Attributes dict.
        """
        out: Dict[str, Any] = {}
        out["instance_id"] = existing.get("InstanceId", "")
        out["instance_type"] = existing.get("InstanceType", "")
        out["state"] = existing.get("State", {}).get("Name", "")
        out["private_ip"] = existing.get("PrivateIpAddress", "")
        out["public_ip"] = existing.get("PublicIpAddress", "")
        out["subnet_id"] = existing.get("SubnetId", "")
        out["vpc_id"] = existing.get("VpcId", "")
        rtnval = out
        return rtnval

    @staticmethod
    def _vpn_device_id_from_tags(*, existing: Dict[str, Any]
                                 ) -> Optional[str]:
        """
            Read the recorded vpn-device-id tag, if any.

            :param existing: AWS describe-instances entry.

            :returns: The device id string or None.
        """
        tag_flat = tag_dict_from_aws(aws_tags=existing.get("Tags", []))
        value = tag_flat.get("automojo:vpn-device-id", None)
        if value is None or len(value) == 0:
            rtnval: Optional[str] = None
            return rtnval
        rtnval = value
        return rtnval

    def destroy(self, *, run_id: str, aspects: Any) -> List[Dict[str, Any]]:
        """
            Terminate every owned instance and return per-instance vpn info.

            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of dicts ``{"instance_id", "vpn_device_id",
                      "had_vpn_join"}``.
        """
        client = self._ec2()
        owner_only = [
            {"Name": "tag:automojo:owned-by",
             "Values": ["automojo-provisioning"]},
            {"Name": "tag:automojo:owner", "Values": [run_id]},
        ]
        response = client.describe_instances(Filters=owner_only)
        ids: List[str] = []
        records: List[Dict[str, Any]] = []
        for reservation in response.get("Reservations", []):
            for entry in reservation.get("Instances", []):
                iid = entry.get("InstanceId", "")
                state = entry.get("State", {}).get("Name", "")
                if state == "terminated":
                    continue
                ids.append(iid)
                tag_flat = tag_dict_from_aws(aws_tags=entry.get("Tags", []))
                records.append({
                    "instance_id": iid,
                    "vpn_device_id": tag_flat.get(
                        "automojo:vpn-device-id", None
                    ),
                    "had_vpn_join": tag_flat.get(
                        "automojo:vpn-provider", None
                    ) is not None,
                })

        if len(ids) > 0:
            try:
                client.terminate_instances(InstanceIds=ids)
            except Exception:
                pass

        rtnval = records
        return rtnval

    def list_owned(self, *, run_id: str) -> List[ProvisionedResource]:
        """
            Return every owned instance for the run.

            :param run_id: Run identifier.

            :returns: List of ProvisionedResource entries.
        """
        client = self._ec2()
        owner_only = [
            {"Name": "tag:automojo:owned-by",
             "Values": ["automojo-provisioning"]},
            {"Name": "tag:automojo:owner", "Values": [run_id]},
        ]
        response = client.describe_instances(Filters=owner_only)
        out: List[ProvisionedResource] = []
        for reservation in response.get("Reservations", []):
            for entry in reservation.get("Instances", []):
                tag_flat = tag_dict_from_aws(aws_tags=entry.get("Tags", []))
                name = tag_flat.get(RESOURCE_NAME_TAG_KEY, "")
                if len(name) == 0:
                    continue
                if entry.get("State", {}).get("Name", "") == "terminated":
                    continue
                attributes = self._instance_attributes(existing=entry)
                resource = ProvisionedResource(
                    kind=self.KIND, name=name,
                    venue_id=entry.get("InstanceId", ""),
                    attributes=attributes,
                    tags=from_aws(aws_tags=entry.get("Tags", [])),
                )
                out.append(resource)
        rtnval = out
        return rtnval
