"""
    .. module:: _fakeaws
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: In-memory fakes for the AWS service clients.

    These replace ``moto``, which mocks at the boto3 layer and therefore only
    works while the venue makes boto3 calls.  With the venue on its own client
    there is nothing for moto to intercept, so the fake is injected through the
    provisioner's ``session_factory`` seam — the same way every other venue's
    tests already work.

    Response shapes match what the resource managers read, in botocore's
    modelled spelling: ``Vpcs``, ``Reservations`` / ``Instances``, ``Tags``,
    ``TagSet`` and so on.  Getting one of those names wrong here would produce
    a green suite over a broken venue, which is the exact failure this fleet
    has been full of, so the names are taken from the managers rather than
    guessed.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import itertools

from typing import Any, Dict, List, Optional

from ccai.restclient.aws.awserror import ClientError


def _tags_of(entry: Dict[str, Any]) -> List[Dict[str, str]]:
    """
        Read an entry's tag list.

        :param entry: The stored resource.

        :returns: The tag list.
    """
    rtnval = entry.get("Tags", []) or []
    return rtnval


def _tag_value(entry: Dict[str, Any], key: str) -> Optional[str]:
    """
        Read one tag value off an entry.

        :param entry: The stored resource.
        :param key: The tag key.

        :returns: The value, or None.
    """
    for tag in _tags_of(entry):
        if tag.get("Key", None) == key:
            rtnval = tag.get("Value", None)
            return rtnval

    rtnval = None
    return rtnval


def _tags_from_specs(specs: Any) -> List[Dict[str, str]]:
    """
        Flatten TagSpecifications into a tag list.

        EC2 accepts tags at create time nested under a resource type, which is
        how the venue tags everything it makes; a fake that ignored them would
        make every owned-resource lookup miss.

        :param specs: The ``TagSpecifications`` argument.

        :returns: The flattened tag list.
    """
    collected: List[Dict[str, str]] = []

    for spec in specs or []:
        for tag in spec.get("Tags", []) or []:
            collected.append({"Key": tag.get("Key", ""),
                              "Value": tag.get("Value", "")})

    rtnval = collected
    return rtnval


def _matches_filters(entry: Dict[str, Any], filters: Any) -> bool:
    """
        Report whether a stored resource satisfies a filter list.

        Only the filter kinds the venue uses are honoured — ``tag:<key>``,
        ``instance-state-name`` and ``name``.  An unrecognised filter is
        treated as NOT matching rather than ignored: silently passing an
        unsupported filter would make a test assert against a listing that the
        real API would have narrowed.

        :param entry: The stored resource.
        :param filters: The ``Filters`` argument.

        :returns: True when every filter matches.
    """
    for entry_filter in filters or []:
        name = entry_filter.get("Name", "")
        wanted = [str(value) for value in
                  (entry_filter.get("Values", []) or [])]

        if name.startswith("tag:") is True:
            found = _tag_value(entry, name[4:])
            if found is None or found not in wanted:
                rtnval = False
                return rtnval
            continue

        if name == "instance-state-name":
            state = (entry.get("State", {}) or {}).get("Name", "")
            if state not in wanted:
                rtnval = False
                return rtnval
            continue

        if name == "name":
            if str(entry.get("Name", "")) not in wanted:
                rtnval = False
                return rtnval
            continue

        # Unknown filter: refuse to match rather than quietly widen the
        # listing beyond what the real API would return.
        rtnval = False
        return rtnval

    rtnval = True
    return rtnval


class FakeEc2Client:
    """
        In-memory EC2.

        Resources live in per-kind dicts keyed by id.  Ids are sequential and
        prefixed the way EC2's are, because the venue records them as venue
        ids and a few assertions read them back.
    """

    def __init__(self) -> None:
        """
            Construct a FakeEc2Client.
        """
        self._counter = itertools.count(1)
        self.vpcs: Dict[str, Dict[str, Any]] = {}
        self.subnets: Dict[str, Dict[str, Any]] = {}
        self.route_tables: Dict[str, Dict[str, Any]] = {}
        self.internet_gateways: Dict[str, Dict[str, Any]] = {}
        self.security_groups: Dict[str, Dict[str, Any]] = {}
        self.instances: Dict[str, Dict[str, Any]] = {}
        self.volumes: Dict[str, Dict[str, Any]] = {}
        self.key_pairs: Dict[str, Dict[str, Any]] = {}
        self.placement_groups: Dict[str, Dict[str, Any]] = {}
        self.images: List[Dict[str, Any]] = [
            {"ImageId": "ami-00000001", "Name": "ubuntu-24.04-base",
             "CreationDate": "2026-01-01T00:00:00.000Z"},
            {"ImageId": "ami-00000002", "Name": "ubuntu-24.04-newer",
             "CreationDate": "2026-06-01T00:00:00.000Z"},
        ]
        return

    def _next_id(self, prefix: str) -> str:
        """
            Mint a sequential resource id.

            :param prefix: The id prefix, e.g. ``vpc``.

            :returns: The id.
        """
        rtnval = "{}-{:08d}".format(prefix, next(self._counter))
        return rtnval

    # -- vpcs ----------------------------------------------------------

    def create_vpc(self, *, CidrBlock: str = "", TagSpecifications: Any = None,
                   **kwargs: Any) -> Dict[str, Any]:
        vpc_id = self._next_id("vpc")
        entry = {"VpcId": vpc_id, "CidrBlock": CidrBlock,
                 "State": "available",
                 "Tags": _tags_from_specs(TagSpecifications)}
        self.vpcs[vpc_id] = entry
        rtnval = {"Vpc": dict(entry)}
        return rtnval

    def describe_vpcs(self, *, Filters: Any = None, VpcIds: Any = None,
                      **kwargs: Any) -> Dict[str, Any]:
        found = self._select(self.vpcs, Filters, VpcIds, "VpcId")
        rtnval = {"Vpcs": found}
        return rtnval

    def delete_vpc(self, *, VpcId: str, **kwargs: Any) -> Dict[str, Any]:
        self.vpcs.pop(VpcId, None)
        return {}

    # -- subnets -------------------------------------------------------

    def create_subnet(self, *, VpcId: str = "", CidrBlock: str = "",
                      AvailabilityZone: str = "",
                      TagSpecifications: Any = None,
                      **kwargs: Any) -> Dict[str, Any]:
        subnet_id = self._next_id("subnet")
        entry = {"SubnetId": subnet_id, "VpcId": VpcId,
                 "CidrBlock": CidrBlock,
                 "AvailabilityZone": AvailabilityZone,
                 "Tags": _tags_from_specs(TagSpecifications)}
        self.subnets[subnet_id] = entry
        rtnval = {"Subnet": dict(entry)}
        return rtnval

    def describe_subnets(self, *, Filters: Any = None, SubnetIds: Any = None,
                         **kwargs: Any) -> Dict[str, Any]:
        rtnval = {"Subnets": self._select(self.subnets, Filters, SubnetIds,
                                          "SubnetId")}
        return rtnval

    def delete_subnet(self, *, SubnetId: str,
                      **kwargs: Any) -> Dict[str, Any]:
        self.subnets.pop(SubnetId, None)
        return {}

    # -- route tables --------------------------------------------------

    def create_route_table(self, *, VpcId: str = "",
                           TagSpecifications: Any = None,
                           **kwargs: Any) -> Dict[str, Any]:
        rt_id = self._next_id("rtb")
        entry = {"RouteTableId": rt_id, "VpcId": VpcId, "Associations": [],
                 "Routes": [],
                 "Tags": _tags_from_specs(TagSpecifications)}
        self.route_tables[rt_id] = entry
        rtnval = {"RouteTable": dict(entry)}
        return rtnval

    def describe_route_tables(self, *, Filters: Any = None,
                              RouteTableIds: Any = None,
                              **kwargs: Any) -> Dict[str, Any]:
        rtnval = {"RouteTables": self._select(self.route_tables, Filters,
                                              RouteTableIds,
                                              "RouteTableId")}
        return rtnval

    def create_route(self, *, RouteTableId: str = "",
                     DestinationCidrBlock: str = "",
                     **kwargs: Any) -> Dict[str, Any]:
        entry = self.route_tables.get(RouteTableId, None)
        if entry is not None:
            entry["Routes"].append(
                {"DestinationCidrBlock": DestinationCidrBlock})
        return {"Return": True}

    def associate_route_table(self, *, RouteTableId: str = "",
                              SubnetId: str = "",
                              **kwargs: Any) -> Dict[str, Any]:
        association_id = self._next_id("rtbassoc")
        entry = self.route_tables.get(RouteTableId, None)
        if entry is not None:
            entry["Associations"].append(
                {"RouteTableAssociationId": association_id,
                 "SubnetId": SubnetId, "Main": False})
        rtnval = {"AssociationId": association_id}
        return rtnval

    def disassociate_route_table(self, *, AssociationId: str,
                                 **kwargs: Any) -> Dict[str, Any]:
        for entry in self.route_tables.values():
            entry["Associations"] = [
                association for association in entry["Associations"]
                if association.get("RouteTableAssociationId", "")
                != AssociationId]
        return {}

    def delete_route_table(self, *, RouteTableId: str,
                           **kwargs: Any) -> Dict[str, Any]:
        self.route_tables.pop(RouteTableId, None)
        return {}

    # -- internet gateways ---------------------------------------------

    def create_internet_gateway(self, *, TagSpecifications: Any = None,
                                **kwargs: Any) -> Dict[str, Any]:
        igw_id = self._next_id("igw")
        entry = {"InternetGatewayId": igw_id, "Attachments": [],
                 "Tags": _tags_from_specs(TagSpecifications)}
        self.internet_gateways[igw_id] = entry
        rtnval = {"InternetGateway": dict(entry)}
        return rtnval

    def describe_internet_gateways(self, *, Filters: Any = None,
                                   InternetGatewayIds: Any = None,
                                   **kwargs: Any) -> Dict[str, Any]:
        rtnval = {"InternetGateways": self._select(
            self.internet_gateways, Filters, InternetGatewayIds,
            "InternetGatewayId")}
        return rtnval

    def attach_internet_gateway(self, *, InternetGatewayId: str = "",
                                VpcId: str = "",
                                **kwargs: Any) -> Dict[str, Any]:
        entry = self.internet_gateways.get(InternetGatewayId, None)
        if entry is not None:
            entry["Attachments"].append({"VpcId": VpcId,
                                         "State": "available"})
        return {}

    def detach_internet_gateway(self, *, InternetGatewayId: str = "",
                                VpcId: str = "",
                                **kwargs: Any) -> Dict[str, Any]:
        entry = self.internet_gateways.get(InternetGatewayId, None)
        if entry is not None:
            entry["Attachments"] = [
                attachment for attachment in entry["Attachments"]
                if attachment.get("VpcId", "") != VpcId]
        return {}

    def delete_internet_gateway(self, *, InternetGatewayId: str,
                                **kwargs: Any) -> Dict[str, Any]:
        self.internet_gateways.pop(InternetGatewayId, None)
        return {}

    # -- security groups -----------------------------------------------

    def create_security_group(self, *, GroupName: str = "",
                              Description: str = "", VpcId: str = "",
                              TagSpecifications: Any = None,
                              **kwargs: Any) -> Dict[str, Any]:
        group_id = self._next_id("sg")
        entry = {"GroupId": group_id, "GroupName": GroupName,
                 "Description": Description, "VpcId": VpcId,
                 "IpPermissions": [], "IpPermissionsEgress": [],
                 "Tags": _tags_from_specs(TagSpecifications)}
        self.security_groups[group_id] = entry
        rtnval = {"GroupId": group_id}
        return rtnval

    def describe_security_groups(self, *, Filters: Any = None,
                                 GroupIds: Any = None,
                                 **kwargs: Any) -> Dict[str, Any]:
        rtnval = {"SecurityGroups": self._select(self.security_groups,
                                                 Filters, GroupIds,
                                                 "GroupId")}
        return rtnval

    def authorize_security_group_ingress(self, *, GroupId: str = "",
                                         IpPermissions: Any = None,
                                         **kwargs: Any) -> Dict[str, Any]:
        entry = self.security_groups.get(GroupId, None)
        if entry is not None:
            entry["IpPermissions"].extend(IpPermissions or [])
        return {"Return": True}

    def authorize_security_group_egress(self, *, GroupId: str = "",
                                        IpPermissions: Any = None,
                                        **kwargs: Any) -> Dict[str, Any]:
        entry = self.security_groups.get(GroupId, None)
        if entry is not None:
            entry["IpPermissionsEgress"].extend(IpPermissions or [])
        return {"Return": True}

    def delete_security_group(self, *, GroupId: str,
                              **kwargs: Any) -> Dict[str, Any]:
        self.security_groups.pop(GroupId, None)
        return {}

    # -- key pairs -----------------------------------------------------

    def import_key_pair(self, *, KeyName: str = "",
                        PublicKeyMaterial: Any = None,
                        TagSpecifications: Any = None,
                        **kwargs: Any) -> Dict[str, Any]:
        key_id = self._next_id("key")
        entry = {"KeyPairId": key_id, "KeyName": KeyName,
                 "KeyFingerprint": "fp-{}".format(KeyName),
                 "Tags": _tags_from_specs(TagSpecifications)}
        self.key_pairs[KeyName] = entry
        rtnval = dict(entry)
        return rtnval

    def describe_key_pairs(self, *, Filters: Any = None,
                           KeyNames: Any = None,
                           **kwargs: Any) -> Dict[str, Any]:
        found = self._select(self.key_pairs, Filters, KeyNames, "KeyName")
        rtnval = {"KeyPairs": found}
        return rtnval

    def delete_key_pair(self, *, KeyName: str = "",
                        **kwargs: Any) -> Dict[str, Any]:
        self.key_pairs.pop(KeyName, None)
        return {}

    # -- placement groups ----------------------------------------------

    def create_placement_group(self, *, GroupName: str = "",
                               Strategy: str = "",
                               TagSpecifications: Any = None,
                               **kwargs: Any) -> Dict[str, Any]:
        entry = {"GroupName": GroupName, "Strategy": Strategy,
                 "State": "available",
                 "Tags": _tags_from_specs(TagSpecifications)}
        self.placement_groups[GroupName] = entry
        rtnval = {"PlacementGroup": dict(entry)}
        return rtnval

    def describe_placement_groups(self, *, Filters: Any = None,
                                  GroupNames: Any = None,
                                  **kwargs: Any) -> Dict[str, Any]:
        rtnval = {"PlacementGroups": self._select(self.placement_groups,
                                                  Filters, GroupNames,
                                                  "GroupName")}
        return rtnval

    def delete_placement_group(self, *, GroupName: str = "",
                               **kwargs: Any) -> Dict[str, Any]:
        self.placement_groups.pop(GroupName, None)
        return {}

    # -- instances -----------------------------------------------------

    def run_instances(self, *, ImageId: str = "", InstanceType: str = "",
                      MinCount: int = 1, MaxCount: int = 1,
                      KeyName: str = "", UserData: Any = None,
                      SubnetId: str = "", SecurityGroupIds: Any = None,
                      TagSpecifications: Any = None,
                      Placement: Any = None,
                      InstanceMarketOptions: Any = None,
                      NetworkInterfaces: Any = None,
                      **kwargs: Any) -> Dict[str, Any]:
        created: List[Dict[str, Any]] = []

        for _ in range(max(1, int(MinCount))):
            instance_id = self._next_id("i")
            entry: Dict[str, Any] = {
                "InstanceId": instance_id,
                "ImageId": ImageId,
                "InstanceType": InstanceType,
                "KeyName": KeyName,
                "SubnetId": SubnetId,
                "State": {"Code": 16, "Name": "running"},
                "PrivateIpAddress": "10.0.0.{}".format(
                    len(self.instances) + 5),
                "PublicIpAddress": "203.0.113.{}".format(
                    len(self.instances) + 5),
                "Placement": Placement or {},
                "NetworkInterfaces": NetworkInterfaces or [],
                "Tags": _tags_from_specs(TagSpecifications),
            }
            if UserData is not None:
                entry["UserData"] = UserData
            if InstanceMarketOptions is not None:
                entry["InstanceMarketOptions"] = InstanceMarketOptions

            self.instances[instance_id] = entry
            created.append(dict(entry))

        rtnval = {"Instances": created}
        return rtnval

    def describe_instances(self, *, Filters: Any = None,
                           InstanceIds: Any = None,
                           **kwargs: Any) -> Dict[str, Any]:
        found = self._select(self.instances, Filters, InstanceIds,
                             "InstanceId")

        # Real EC2 nests instances under reservations, and the venue walks
        # that nesting; returning a flat list would make every lookup miss.
        rtnval = {"Reservations": [{"ReservationId": "r-fake",
                                    "Instances": found}]}
        return rtnval

    def terminate_instances(self, *, InstanceIds: Any = None,
                            **kwargs: Any) -> Dict[str, Any]:
        changed: List[Dict[str, Any]] = []
        for instance_id in InstanceIds or []:
            entry = self.instances.pop(instance_id, None)
            if entry is not None:
                changed.append({
                    "InstanceId": instance_id,
                    "CurrentState": {"Code": 48, "Name": "terminated"}})
        rtnval = {"TerminatingInstances": changed}
        return rtnval

    # -- volumes -------------------------------------------------------

    def create_volume(self, *, AvailabilityZone: str = "", Size: int = 0,
                      VolumeType: str = "", TagSpecifications: Any = None,
                      **kwargs: Any) -> Dict[str, Any]:
        volume_id = self._next_id("vol")
        entry = {"VolumeId": volume_id, "Size": Size,
                 "VolumeType": VolumeType,
                 "AvailabilityZone": AvailabilityZone,
                 "State": "available", "Attachments": [],
                 "Tags": _tags_from_specs(TagSpecifications)}
        self.volumes[volume_id] = entry
        rtnval = dict(entry)
        return rtnval

    def describe_volumes(self, *, Filters: Any = None, VolumeIds: Any = None,
                         **kwargs: Any) -> Dict[str, Any]:
        rtnval = {"Volumes": self._select(self.volumes, Filters, VolumeIds,
                                          "VolumeId")}
        return rtnval

    def attach_volume(self, *, VolumeId: str = "", InstanceId: str = "",
                      Device: str = "", **kwargs: Any) -> Dict[str, Any]:
        entry = self.volumes.get(VolumeId, None)
        if entry is not None:
            entry["Attachments"] = [{"VolumeId": VolumeId,
                                     "InstanceId": InstanceId,
                                     "Device": Device,
                                     "State": "attached"}]
        rtnval = {"VolumeId": VolumeId, "InstanceId": InstanceId,
                  "State": "attached"}
        return rtnval

    def detach_volume(self, *, VolumeId: str = "",
                      **kwargs: Any) -> Dict[str, Any]:
        entry = self.volumes.get(VolumeId, None)
        if entry is not None:
            entry["Attachments"] = []
        rtnval = {"VolumeId": VolumeId, "State": "detached"}
        return rtnval

    def delete_volume(self, *, VolumeId: str,
                      **kwargs: Any) -> Dict[str, Any]:
        self.volumes.pop(VolumeId, None)
        return {}

    # -- images --------------------------------------------------------

    def describe_images(self, *, Filters: Any = None, ImageIds: Any = None,
                        Owners: Any = None,
                        **kwargs: Any) -> Dict[str, Any]:
        found: List[Dict[str, Any]] = []
        for entry in self.images:
            if ImageIds is not None and entry["ImageId"] not in ImageIds:
                continue
            if Filters is not None:
                if _matches_filters(entry, Filters) is False:
                    continue
            found.append(dict(entry))

        rtnval = {"Images": found}
        return rtnval

    # -- selection -----------------------------------------------------

    def _select(self, store: Dict[str, Dict[str, Any]], filters: Any,
                ids: Any, id_field: str) -> List[Dict[str, Any]]:
        """
            Select stored resources by explicit ids and/or filters.

            :param store: The per-kind store.
            :param filters: The ``Filters`` argument.
            :param ids: The explicit-id argument.
            :param id_field: The field carrying the id.

            :returns: The matching resources, copied.
        """
        found: List[Dict[str, Any]] = []

        for entry in store.values():
            if ids is not None and len(ids) > 0:
                if entry.get(id_field, None) not in ids:
                    continue
            if filters is not None and len(filters) > 0:
                if _matches_filters(entry, filters) is False:
                    continue
            found.append(dict(entry))

        rtnval = found
        return rtnval


class FakeS3Client:
    """
        In-memory S3, bucket level only.
    """

    def __init__(self) -> None:
        """
            Construct a FakeS3Client.
        """
        self.buckets: Dict[str, Dict[str, Any]] = {}
        return

    def head_bucket(self, *, Bucket: str, **kwargs: Any) -> Dict[str, Any]:
        if Bucket not in self.buckets:
            raise ClientError(
                "The bucket does not exist. BUCKET: {}".format(Bucket),
                code="404", status=404, detail="Not Found")

        rtnval = {"ResponseMetadata": {"HTTPStatusCode": 200}}
        return rtnval

    def create_bucket(self, *, Bucket: str,
                      CreateBucketConfiguration: Any = None,
                      **kwargs: Any) -> Dict[str, Any]:
        location = ""
        if CreateBucketConfiguration is not None:
            location = CreateBucketConfiguration.get("LocationConstraint", "")

        self.buckets[Bucket] = {"Name": Bucket, "Location": location,
                                "TagSet": []}
        rtnval = {"Location": "/{}".format(Bucket)}
        return rtnval

    def delete_bucket(self, *, Bucket: str,
                      **kwargs: Any) -> Dict[str, Any]:
        self.buckets.pop(Bucket, None)
        return {"ResponseMetadata": {"HTTPStatusCode": 204}}

    def list_buckets(self, **kwargs: Any) -> Dict[str, Any]:
        rtnval = {"Buckets": [{"Name": name}
                              for name in self.buckets.keys()]}
        return rtnval

    def get_bucket_tagging(self, *, Bucket: str,
                           **kwargs: Any) -> Dict[str, Any]:
        entry = self.buckets.get(Bucket, None)
        if entry is None:
            raise ClientError(
                "The bucket does not exist. BUCKET: {}".format(Bucket),
                code="NoSuchBucket", status=404, detail="Not Found")

        tags = entry.get("TagSet", []) or []
        if len(tags) == 0:
            # S3 treats "no tags" as an error rather than an empty set, and
            # the venue recovers that one code; answering with an empty list
            # would leave that branch untested.
            raise ClientError(
                "The bucket has no tag set. BUCKET: {}".format(Bucket),
                code="NoSuchTagSet", status=404, detail="Not Found")

        rtnval = {"TagSet": [dict(tag) for tag in tags]}
        return rtnval

    def put_bucket_tagging(self, *, Bucket: str, Tagging: Any = None,
                           **kwargs: Any) -> Dict[str, Any]:
        entry = self.buckets.get(Bucket, None)
        if entry is not None:
            entry["TagSet"] = list((Tagging or {}).get("TagSet", []) or [])
        return {"ResponseMetadata": {"HTTPStatusCode": 204}}


class FakeRoute53Client:
    """
        In-memory Route53.
    """

    def __init__(self, *, zones: Optional[List[Dict[str, str]]] = None
                 ) -> None:
        """
            Construct a FakeRoute53Client.

            :param zones: The hosted zones to present.
        """
        if zones is not None:
            self.zones = list(zones)
        else:
            self.zones = [{"Id": "/hostedzone/Z1FAKE",
                           "Name": "example.com."}]
        self.changes: List[Dict[str, Any]] = []
        return

    def list_hosted_zones(self, **kwargs: Any) -> Dict[str, Any]:
        rtnval = {"HostedZones": [dict(zone) for zone in self.zones]}
        return rtnval

    def change_resource_record_sets(self, *, HostedZoneId: str = "",
                                    ChangeBatch: Any = None,
                                    **kwargs: Any) -> Dict[str, Any]:
        self.changes.append({"HostedZoneId": HostedZoneId,
                             "ChangeBatch": ChangeBatch or {}})
        rtnval = {"ChangeInfo": {"Id": "/change/C1FAKE",
                                 "Status": "PENDING"}}
        return rtnval


class FakeSsmClient:
    """
        In-memory SSM Parameter Store.
    """

    def __init__(self, *, parameters: Optional[Dict[str, str]] = None
                 ) -> None:
        """
            Construct a FakeSsmClient.

            :param parameters: The parameters to present.
        """
        self.parameters: Dict[str, str] = dict(parameters or {})
        return

    def get_parameter(self, *, Name: str, **kwargs: Any) -> Dict[str, Any]:
        value = self.parameters.get(Name, None)
        if value is None:
            # Any /aws/service/ lookup resolves to the seeded AMI, which is
            # what the image resolver expects from the public parameters.
            value = "ami-00000002"

        rtnval = {"Parameter": {"Name": Name, "Value": value}}
        return rtnval


class FakeFsxClient:
    """
        In-memory FSx.
    """

    def __init__(self, *,
                 file_systems: Optional[List[Dict[str, Any]]] = None
                 ) -> None:
        """
            Construct a FakeFsxClient.

            :param file_systems: The file systems to present.
        """
        if file_systems is not None:
            self.file_systems = list(file_systems)
        else:
            self.file_systems = [{
                "FileSystemId": "fs-0fake",
                "DNSName": "fs-0fake.fsx.us-east-2.amazonaws.com",
                "LustreConfiguration": {"MountName": "abcdefgh"},
            }]
        return

    def describe_file_systems(self, *, FileSystemIds: Any = None,
                              **kwargs: Any) -> Dict[str, Any]:
        found: List[Dict[str, Any]] = []
        for entry in self.file_systems:
            if FileSystemIds is not None and len(FileSystemIds) > 0:
                if entry.get("FileSystemId", "") not in FileSystemIds:
                    continue
            found.append(dict(entry))

        rtnval = {"FileSystems": found}
        return rtnval


class FakeAwsSessionFactory:
    """
        A session factory serving the in-memory clients.

        Presents the same ``client(service_name=)`` surface the real factory
        does, so the venue is exercised through its own seam rather than
        through a patched SDK.
    """

    def __init__(self, *, region: str = "us-east-2") -> None:
        """
            Construct a FakeAwsSessionFactory.

            :param region: The region the venue believes it is in.
        """
        self.region: str = region
        self.ec2 = FakeEc2Client()
        self.s3 = FakeS3Client()
        self.route53 = FakeRoute53Client()
        self.ssm = FakeSsmClient()
        self.fsx = FakeFsxClient()

        self._clients: Dict[str, Any] = {
            "ec2": self.ec2, "s3": self.s3, "route53": self.route53,
            "ssm": self.ssm, "fsx": self.fsx,
        }
        return

    def client(self, *, service_name: str) -> Any:
        """
            Return the fake client for a service.

            :param service_name: The service identifier.

            :returns: The fake client.

            :raises: ValueError for an unmodelled service, so a venue change
                that reaches for a new one fails loudly here rather than
                silently receiving a stub.
        """
        found = self._clients.get(service_name, None)
        if found is None:
            err_msg = ("FakeAwsSessionFactory has no client for {!r}; add one "
                       "rather than letting the call vanish.".format(
                           service_name))
            raise ValueError(err_msg)

        rtnval = found
        return rtnval

    def register_client(self, *, service_name: str, client: Any) -> None:
        """
            Replace one fake client.

            :param service_name: The service identifier.
            :param client: The replacement.
        """
        self._clients[service_name] = client
        return
