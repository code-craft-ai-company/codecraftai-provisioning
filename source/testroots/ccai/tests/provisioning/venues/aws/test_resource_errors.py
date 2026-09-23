"""
    .. module:: test_resource_errors
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Pins which EC2 / FSx errors the AWS resource managers tolerate
               on their create / attach / describe steps and which they let
               propagate.

    Each manager tolerates only the one idempotency answer its step can
    legitimately receive on a re-apply; every other error must reach the
    caller rather than being reported as a successful create.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from ccai import testbase

from ccai.restclient.aws.awserror import ClientError

from ccai.interfaces.cloudsharedfilesystem import CloudSharedFilesystem
from ccai.provisioning.model.cloud.cloudegressrule import CloudEgressRule
from ccai.provisioning.model.cloud.cloudingressrule import CloudIngressRule
from ccai.provisioning.model.cloud.cloudsecuritygroup import (
    CloudSecurityGroup
)
from ccai.provisioning.model.cloud.cloudstoragevolume import (
    CloudStorageVolume
)
from ccai.provisioning.model.cloud.cloudsubnet import CloudSubnet
from ccai.provisioning.venues.aws.awserrors import AwsValidationError
from ccai.provisioning.venues.aws.resources.fsxmanager import FsxManager
from ccai.provisioning.venues.aws.resources.placementgroupmanager import (
    PlacementGroupManager
)
from ccai.provisioning.venues.aws.resources.securitygroupmanager import (
    SecurityGroupManager
)
from ccai.provisioning.venues.aws.resources.subnetmanager import (
    SubnetManager
)
from ccai.provisioning.venues.aws.resources.volumemanager import (
    VolumeManager
)

from ccai.tests.provisioning.venues.aws._fakeaws import (
    FakeAwsSessionFactory, FakeEc2Client, FakeFsxClient
)


_RUN_ID = "run01"


def _client_error(*, code: str) -> ClientError:
    """
        Build a ClientError carrying an EC2 error code.

        :param code: The AWS error code.

        :returns: The ClientError.
    """
    rtnval = ClientError("The AWS request failed. CODE: {}".format(code),
                         code=code, status=400, detail=code)
    return rtnval


def _has_rule(*, permissions: List[Dict[str, Any]], protocol: str,
              from_port: Optional[int], to_port: Optional[int],
              cidr: str) -> bool:
    """
        Report whether a permission list already grants a protocol / port /
        CIDR combination, the way EC2 compares rules for duplicates.

        :param permissions: Stored IpPermissions.
        :param protocol: The IpProtocol.
        :param from_port: The FromPort, or None.
        :param to_port: The ToPort, or None.
        :param cidr: The CIDR.

        :returns: True when the rule is already present.
    """
    for permission in permissions:
        if permission.get("IpProtocol", "") != protocol:
            continue
        if permission.get("FromPort", None) != from_port:
            continue
        if permission.get("ToPort", None) != to_port:
            continue
        for ip_range in permission.get("IpRanges", []):
            if ip_range.get("CidrIp", "") == cidr:
                rtnval = True
                return rtnval

    rtnval = False
    return rtnval


class _StrictEc2Client(FakeEc2Client):
    """
        A FakeEc2Client that answers the conflicts the managers have to tell
        apart the way EC2 does, and that can be told to fail an operation.
    """

    def __init__(self) -> None:
        """
            Construct a _StrictEc2Client.
        """
        super().__init__()
        self.failures: Dict[str, ClientError] = {}
        return

    def _raise_injected(self, *, operation: str) -> None:
        """
            Raise the failure injected for an operation, if any.

            :param operation: The EC2 operation name.
        """
        failure = self.failures.get(operation, None)
        if failure is not None:
            raise failure
        return

    def create_security_group(self, **kwargs: Any) -> Dict[str, Any]:
        rtnval = super().create_security_group(**kwargs)

        # EC2 gives every new VPC security group an allow-all egress rule.
        entry = self.security_groups[rtnval["GroupId"]]
        entry["IpPermissionsEgress"].append(
            {"IpProtocol": "-1", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]})
        return rtnval

    def authorize_security_group_ingress(self, **kwargs: Any
                                         ) -> Dict[str, Any]:
        self._raise_injected(operation="authorize_security_group_ingress")
        rtnval = super().authorize_security_group_ingress(**kwargs)
        return rtnval

    def authorize_security_group_egress(self, *, GroupId: str = "",
                                        IpPermissions: Any = None,
                                        **kwargs: Any) -> Dict[str, Any]:
        self._raise_injected(operation="authorize_security_group_egress")

        # EC2 authorizes the batch atomically: one duplicate rejects it all.
        stored = self.security_groups[GroupId]["IpPermissionsEgress"]
        for permission in IpPermissions or []:
            for ip_range in permission.get("IpRanges", []):
                duplicate = _has_rule(
                    permissions=stored,
                    protocol=permission.get("IpProtocol", ""),
                    from_port=permission.get("FromPort", None),
                    to_port=permission.get("ToPort", None),
                    cidr=ip_range.get("CidrIp", ""))
                if duplicate is True:
                    raise _client_error(code="InvalidPermission.Duplicate")

        rtnval = super().authorize_security_group_egress(
            GroupId=GroupId, IpPermissions=IpPermissions, **kwargs)
        return rtnval

    def create_route(self, **kwargs: Any) -> Dict[str, Any]:
        self._raise_injected(operation="create_route")
        rtnval = super().create_route(**kwargs)
        return rtnval

    def associate_route_table(self, *, RouteTableId: str = "",
                              SubnetId: str = "",
                              **kwargs: Any) -> Dict[str, Any]:
        self._raise_injected(operation="associate_route_table")

        # A subnet carries one explicit association; EC2 refuses a second
        # one whichever table already holds it.
        for table in self.route_tables.values():
            for association in table["Associations"]:
                if association.get("SubnetId", "") == SubnetId:
                    raise _client_error(code="Resource.AlreadyAssociated")

        rtnval = super().associate_route_table(
            RouteTableId=RouteTableId, SubnetId=SubnetId, **kwargs)
        return rtnval

    def attach_volume(self, *, VolumeId: str = "", InstanceId: str = "",
                      Device: str = "", **kwargs: Any) -> Dict[str, Any]:
        self._raise_injected(operation="attach_volume")

        # EC2 answers VolumeInUse for an attached volume whichever instance
        # holds it.
        entry = self.volumes.get(VolumeId, None)
        if entry is not None and len(entry["Attachments"]) > 0:
            raise _client_error(code="VolumeInUse")

        rtnval = super().attach_volume(VolumeId=VolumeId,
                                       InstanceId=InstanceId,
                                       Device=Device, **kwargs)
        return rtnval

    def create_placement_group(self, **kwargs: Any) -> Dict[str, Any]:
        self._raise_injected(operation="create_placement_group")
        rtnval = super().create_placement_group(**kwargs)
        return rtnval


class _MissingFileSystemFsxClient(FakeFsxClient):
    """
        A FakeFsxClient that answers the way FSx does for an unknown id.
    """

    def describe_file_systems(self, *, FileSystemIds: Any = None,
                              **kwargs: Any) -> Dict[str, Any]:
        raise _client_error(code="FileSystemNotFound")


def _factory_with(*, ec2: _StrictEc2Client) -> FakeAwsSessionFactory:
    """
        Build a session factory serving a strict EC2 fake.

        :param ec2: The EC2 fake.

        :returns: The session factory.
    """
    factory = FakeAwsSessionFactory()
    factory.register_client(service_name="ec2", client=ec2)
    rtnval = factory
    return rtnval


def _public_subnet(*, public: bool) -> CloudSubnet:
    """
        Build the subnet the SubnetManager tests ensure.

        :param public: Whether the subnet routes through the IGW.

        :returns: The CloudSubnet.
    """
    rtnval = CloudSubnet(name="sub-a", network="vpc-a", cidr="10.0.1.0/24",
                         zone="us-east-2a", public=public)
    return rtnval


def _ensure_subnet(*, manager: SubnetManager, public: bool) -> Any:
    """
        Run SubnetManager.ensure for the test subnet.

        :param manager: The SubnetManager.
        :param public: Whether the subnet routes through the IGW.

        :returns: The ProvisionedResource.
    """
    rtnval = manager.ensure(desired=_public_subnet(public=public),
                            run_id=_RUN_ID, vpc_id="vpc-1", igw_id="igw-1",
                            default_tags={}, aspects=None)
    return rtnval


def _ensure_volume(*, manager: VolumeManager, instance_id: str) -> Any:
    """
        Run VolumeManager.ensure for the test volume.

        :param manager: The VolumeManager.
        :param instance_id: The instance to attach to.

        :returns: The ProvisionedResource.
    """
    desired = CloudStorageVolume(name="vol-a", size_gb=64,
                                 attached_to="inst-a", mount="/dev/sdf")
    rtnval = manager.ensure(desired=desired, run_id=_RUN_ID,
                            availability_zone="us-east-2a", default_tags={},
                            attach_instance_id=instance_id, aspects=None)
    return rtnval


# ----------------------------------------------------------------------
# security groups
# ----------------------------------------------------------------------

def test_sg_ingress_failure_propagates() -> None:
    """
        A failure authorizing ingress on a new group reaches the caller.
    """
    ec2 = _StrictEc2Client()
    ec2.failures["authorize_security_group_ingress"] = _client_error(
        code="InvalidParameterValue")
    manager = SecurityGroupManager(session_factory=_factory_with(ec2=ec2))

    rule = CloudIngressRule(protocol="tcp", from_port=22, to_port=22,
                            source_cidrs=["0.0.0.0/0"])
    desired = CloudSecurityGroup(name="sg-a", network="vpc-a",
                                 ingress_rules=[rule])

    with testbase.raises(ClientError) as caught:
        manager.ensure(desired=desired, run_id=_RUN_ID, vpc_id="vpc-1",
                       default_tags={}, aspects=None)

    assert caught.exception.code == "InvalidParameterValue"
    return


def test_sg_egress_failure_propagates() -> None:
    """
        A non-duplicate failure authorizing egress reaches the caller.
    """
    ec2 = _StrictEc2Client()
    ec2.failures["authorize_security_group_egress"] = _client_error(
        code="InvalidParameterValue")
    manager = SecurityGroupManager(session_factory=_factory_with(ec2=ec2))

    rule = CloudEgressRule(protocol="tcp", from_port=443, to_port=443,
                           dest_cidrs=["10.0.0.0/8"])
    desired = CloudSecurityGroup(name="sg-a", network="vpc-a",
                                 egress_rules=[rule])

    with testbase.raises(ClientError) as caught:
        manager.ensure(desired=desired, run_id=_RUN_ID, vpc_id="vpc-1",
                       default_tags={}, aspects=None)

    assert caught.exception.code == "InvalidParameterValue"
    return


def test_sg_default_egress_duplicate_keeps_other_rules() -> None:
    """
        Requesting the allow-all egress rule EC2 already created is tolerated
        and does not drop the other egress rules of the request.
    """
    ec2 = _StrictEc2Client()
    manager = SecurityGroupManager(session_factory=_factory_with(ec2=ec2))

    allow_all = CloudEgressRule(protocol="all", from_port=0, to_port=65535,
                                dest_cidrs=["0.0.0.0/0"])
    https = CloudEgressRule(protocol="tcp", from_port=443, to_port=443,
                            dest_cidrs=["10.0.0.0/8"])
    desired = CloudSecurityGroup(name="sg-a", network="vpc-a",
                                 egress_rules=[allow_all, https])

    resource = manager.ensure(desired=desired, run_id=_RUN_ID,
                              vpc_id="vpc-1", default_tags={}, aspects=None)

    stored = ec2.security_groups[resource.venue_id]["IpPermissionsEgress"]
    assert _has_rule(permissions=stored, protocol="tcp", from_port=443,
                     to_port=443, cidr="10.0.0.0/8") is True
    return


# ----------------------------------------------------------------------
# subnets / public route table
# ----------------------------------------------------------------------

def test_public_route_failure_propagates() -> None:
    """
        A failure adding 0.0.0.0/0 -> IGW to a new route table reaches the
        caller.
    """
    ec2 = _StrictEc2Client()
    ec2.failures["create_route"] = _client_error(
        code="InvalidGatewayID.NotFound")
    manager = SubnetManager(session_factory=_factory_with(ec2=ec2))

    with testbase.raises(ClientError) as caught:
        _ensure_subnet(manager=manager, public=True)

    assert caught.exception.code == "InvalidGatewayID.NotFound"
    return


def test_public_subnet_reapply_tolerates_own_association() -> None:
    """
        Re-applying a public subnet already associated with its route table
        succeeds and leaves one association.
    """
    ec2 = _StrictEc2Client()
    manager = SubnetManager(session_factory=_factory_with(ec2=ec2))

    first = _ensure_subnet(manager=manager, public=True)
    _ensure_subnet(manager=manager, public=True)

    associated = []
    for table in ec2.route_tables.values():
        for association in table["Associations"]:
            if association.get("SubnetId", "") == first.venue_id:
                associated.append(association)
    assert len(associated) == 1
    return


def test_public_subnet_association_with_other_table_propagates() -> None:
    """
        A subnet already associated with a different route table is not
        reported as routed through the public table.
    """
    ec2 = _StrictEc2Client()
    manager = SubnetManager(session_factory=_factory_with(ec2=ec2))

    private = _ensure_subnet(manager=manager, public=False)
    foreign = ec2.create_route_table(VpcId="vpc-1")
    foreign_id = foreign["RouteTable"]["RouteTableId"]
    ec2.associate_route_table(RouteTableId=foreign_id,
                              SubnetId=private.venue_id)

    with testbase.raises(ClientError) as caught:
        _ensure_subnet(manager=manager, public=True)

    assert caught.exception.code == "Resource.AlreadyAssociated"
    return


def test_public_subnet_association_failure_propagates() -> None:
    """
        A non-duplicate failure associating the route table reaches the
        caller.
    """
    ec2 = _StrictEc2Client()
    ec2.failures["associate_route_table"] = _client_error(
        code="InvalidRouteTableID.NotFound")
    manager = SubnetManager(session_factory=_factory_with(ec2=ec2))

    with testbase.raises(ClientError) as caught:
        _ensure_subnet(manager=manager, public=True)

    assert caught.exception.code == "InvalidRouteTableID.NotFound"
    return


# ----------------------------------------------------------------------
# volumes
# ----------------------------------------------------------------------

def test_volume_reapply_tolerates_attachment_to_same_instance() -> None:
    """
        Re-applying a volume already attached to the requested instance
        succeeds.
    """
    ec2 = _StrictEc2Client()
    manager = VolumeManager(session_factory=_factory_with(ec2=ec2))

    first = _ensure_volume(manager=manager, instance_id="i-00000001")
    second = _ensure_volume(manager=manager, instance_id="i-00000001")

    assert second.venue_id == first.venue_id
    return


def test_volume_attached_to_other_instance_propagates() -> None:
    """
        A volume attached to some other instance is not reported as attached
        to the requested one.
    """
    ec2 = _StrictEc2Client()
    manager = VolumeManager(session_factory=_factory_with(ec2=ec2))

    _ensure_volume(manager=manager, instance_id="i-00000001")

    with testbase.raises(ClientError) as caught:
        _ensure_volume(manager=manager, instance_id="i-00000002")

    assert caught.exception.code == "VolumeInUse"
    return


def test_volume_attach_failure_propagates() -> None:
    """
        A non-duplicate failure attaching a volume reaches the caller.
    """
    ec2 = _StrictEc2Client()
    ec2.failures["attach_volume"] = _client_error(code="IncorrectState")
    manager = VolumeManager(session_factory=_factory_with(ec2=ec2))

    with testbase.raises(ClientError) as caught:
        _ensure_volume(manager=manager, instance_id="i-00000001")

    assert caught.exception.code == "IncorrectState"
    return


# ----------------------------------------------------------------------
# placement groups
# ----------------------------------------------------------------------

def test_placement_group_duplicate_is_tolerated() -> None:
    """
        A create answered with InvalidPlacementGroup.Duplicate still returns
        the run-scoped group name.
    """
    ec2 = _StrictEc2Client()
    ec2.failures["create_placement_group"] = _client_error(
        code="InvalidPlacementGroup.Duplicate")
    manager = PlacementGroupManager(session_factory=_factory_with(ec2=ec2))

    name = manager.ensure(run_id=_RUN_ID, logical_name="apod",
                          default_tags={}, aspects=None)

    assert name == "codecraftai-pg-run01-apod"
    return


def test_placement_group_failure_propagates() -> None:
    """
        A non-duplicate failure creating a placement group reaches the
        caller.
    """
    ec2 = _StrictEc2Client()
    ec2.failures["create_placement_group"] = _client_error(
        code="PlacementGroupLimitExceeded")
    manager = PlacementGroupManager(session_factory=_factory_with(ec2=ec2))

    with testbase.raises(ClientError) as caught:
        manager.ensure(run_id=_RUN_ID, logical_name="apod",
                       default_tags={}, aspects=None)

    assert caught.exception.code == "PlacementGroupLimitExceeded"
    return


# ----------------------------------------------------------------------
# FSx
# ----------------------------------------------------------------------

def test_fsx_describe_failure_propagates() -> None:
    """
        A failure describing the existing_id filesystem reaches the caller
        instead of attaching with empty mount data.
    """
    factory = FakeAwsSessionFactory()
    factory.register_client(service_name="fsx",
                            client=_MissingFileSystemFsxClient())
    manager = FsxManager(session_factory=factory)
    desired = CloudSharedFilesystem(name="lus1", kind="LUSTRE",
                                    existing_id="fs-0missing")

    with testbase.raises(ClientError) as caught:
        manager.attach(desired=desired, aspects=None)

    assert caught.exception.code == "FileSystemNotFound"
    return


def test_fsx_unknown_existing_id_is_rejected() -> None:
    """
        An existing_id the describe does not return is refused rather than
        attached with empty mount data.
    """
    manager = FsxManager(session_factory=FakeAwsSessionFactory())
    desired = CloudSharedFilesystem(name="lus1", kind="LUSTRE",
                                    existing_id="fs-0missing")

    with testbase.raises(AwsValidationError) as caught:
        manager.attach(desired=desired, aspects=None)

    assert "fs-0missing" in str(caught.exception)
    return


def test_fsx_existing_id_attaches_with_mount_data() -> None:
    """
        A resolvable existing_id attaches with its DNS and mount names.
    """
    manager = FsxManager(session_factory=FakeAwsSessionFactory())
    desired = CloudSharedFilesystem(name="lus1", kind="LUSTRE",
                                    existing_id="fs-0fake")

    resource = manager.attach(desired=desired, aspects=None)

    assert resource.attributes["mount_name"] == "abcdefgh"
    return
