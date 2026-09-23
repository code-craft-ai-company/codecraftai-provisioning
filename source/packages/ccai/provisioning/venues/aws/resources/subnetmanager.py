"""
    .. module:: subnetmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: AWS Subnet manager for the AWS venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from ccai.restclient.aws.awserror import ClientError

from ccai.provisioning.model.cloud.cloudsubnet import CloudSubnet
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.venues.aws.awsboto3sessionfactory import (
    AwsBoto3SessionFactory
)
from ccai.provisioning.venues.aws.awsidempotency import (
    owner_filters, tag_dict_from_aws
)
from ccai.provisioning.venues.aws.awstagging import (
    base_resource_tags, tag_specifications, from_aws, RESOURCE_NAME_TAG_KEY
)


def _has_subnet_association(*, associations: List[Dict[str, Any]],
                            subnet_id: str) -> bool:
    """
        Report whether a route table's associations include a subnet.

        :param associations: The route table's ``Associations`` entries.
        :param subnet_id: AWS Subnet id.

        :returns: True when the subnet is associated with the table.
    """
    for association in associations:
        if association.get("SubnetId", "") == subnet_id:
            rtnval = True
            return rtnval

    rtnval = False
    return rtnval


class SubnetManager:
    """
        Manager for AWS Subnets.

        Looks up the parent VPC by neutral network name, then creates a
        subnet bound to it.  Honours ``public=True`` by routing through the
        VPC's codecraftai-managed Internet Gateway.
    """

    KIND: str = "subnet"

    def __init__(self, *, session_factory: AwsBoto3SessionFactory) -> None:
        """
            Construct a SubnetManager.

            :param session_factory: AwsBoto3SessionFactory.
        """
        self._session_factory: AwsBoto3SessionFactory = session_factory
        return

    def _ec2(self) -> Any:
        """
            Return the EC2 boto3 client.

            :returns: A boto3 EC2 client.
        """
        rtnval = self._session_factory.client(service_name="ec2")
        return rtnval

    def find(self, *, run_id: str, name: str) -> Optional[Dict[str, Any]]:
        """
            Find an existing owned subnet by run+name tags.

            :param run_id: Run identifier.
            :param name: Neutral subnet name.

            :returns: The describe_subnets ``Subnet`` dict or None.
        """
        client = self._ec2()
        filters = owner_filters(run_id=run_id, resource_name=name)
        response = client.describe_subnets(Filters=filters)
        subnets = response.get("Subnets", [])
        if len(subnets) == 0:
            rtnval: Optional[Dict[str, Any]] = None
            return rtnval
        rtnval = subnets[0]
        return rtnval

    def ensure(self, *, desired: CloudSubnet, run_id: str, vpc_id: str,
               igw_id: str,
               default_tags: List[Dict[str, str]],
               aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for a subnet.

            :param desired: Desired CloudSubnet.
            :param run_id: Run identifier.
            :param vpc_id: AWS VPC id of the parent network.
            :param igw_id: AWS IGW id of the parent network (for public route).
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the subnet.
        """
        client = self._ec2()
        existing = self.find(run_id=run_id, name=desired.name)

        if existing is None:
            neutral_tags = base_resource_tags(
                run_id=run_id, resource_name=desired.name,
                resource_kind=self.KIND, extra=dict(desired.tags),
                defaults=default_tags,
            )
            tag_specs = tag_specifications(
                resource_type="subnet", neutral_tags=neutral_tags
            )
            created = client.create_subnet(
                VpcId=vpc_id,
                CidrBlock=desired.cidr,
                AvailabilityZone=desired.zone,
                TagSpecifications=tag_specs,
            )
            existing = created.get("Subnet", {})

        subnet_id = existing.get("SubnetId", "")

        if desired.public is True:
            self._ensure_public_route(
                run_id=run_id, network_name=desired.network,
                vpc_id=vpc_id, igw_id=igw_id, subnet_id=subnet_id,
                default_tags=default_tags,
            )

        attributes: Dict[str, Any] = {}
        attributes["subnet_id"] = subnet_id
        attributes["vpc_id"] = vpc_id
        attributes["cidr"] = existing.get("CidrBlock", desired.cidr)
        attributes["zone"] = existing.get(
            "AvailabilityZone", desired.zone
        )
        attributes["public"] = desired.public

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=subnet_id,
            attributes=attributes,
            tags=from_aws(aws_tags=existing.get("Tags", [])),
        )
        return rtnval

    def _ensure_public_route(self, *, run_id: str, network_name: str,
                             vpc_id: str, igw_id: str, subnet_id: str,
                             default_tags: List[Dict[str, str]]) -> str:
        """
            Create or reuse a public route table that points 0.0.0.0/0 at IGW.

            :param run_id: Run identifier.
            :param network_name: Parent neutral network name.
            :param vpc_id: AWS VPC id.
            :param igw_id: AWS Internet Gateway id.
            :param subnet_id: AWS Subnet id to associate with the table.
            :param default_tags: Venue default tags.

            :returns: The route table id.
        """
        client = self._ec2()
        rt_name = "{}-public-rt".format(network_name)
        filters = owner_filters(run_id=run_id, resource_name=rt_name)
        response = client.describe_route_tables(Filters=filters)
        tables = response.get("RouteTables", [])
        associations: List[Dict[str, Any]] = []

        if len(tables) > 0:
            rt_id = tables[0].get("RouteTableId", "")
            associations = tables[0].get("Associations", [])
        else:
            neutral_tags = base_resource_tags(
                run_id=run_id, resource_name=rt_name,
                resource_kind="route_table", defaults=default_tags,
            )
            tag_specs = tag_specifications(
                resource_type="route-table", neutral_tags=neutral_tags
            )
            created = client.create_route_table(
                VpcId=vpc_id, TagSpecifications=tag_specs
            )
            rt_id = created.get("RouteTable", {}).get("RouteTableId", "")

            # The table was created a moment ago and holds only its local
            # route, so there is no duplicate to tolerate; any failure is real.
            client.create_route(
                RouteTableId=rt_id,
                DestinationCidrBlock="0.0.0.0/0",
                GatewayId=igw_id,
            )

        try:
            client.associate_route_table(RouteTableId=rt_id,
                                         SubnetId=subnet_id)
        except ClientError as xcpt:
            # A re-apply finds the subnet already associated with this table
            # and EC2 answers Resource.AlreadyAssociated.  EC2 gives the same
            # answer when the subnet belongs to a different table, which would
            # leave it without the public route, so only an association with
            # this table is tolerated.  Any other error is real.
            if xcpt.code != "Resource.AlreadyAssociated":
                raise
            already_here = _has_subnet_association(associations=associations,
                                                   subnet_id=subnet_id)
            if already_here is False:
                raise

        rtnval = rt_id
        return rtnval

    def destroy(self, *, run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned subnet + route table for the run.

            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of destroyed subnet ids.
        """
        client = self._ec2()
        deleted: List[str] = []

        owner_only = [
            {"Name": "tag:ccai:owned-by",
             "Values": ["codecraftai-provisioning"]},
            {"Name": "tag:ccai:owner", "Values": [run_id]},
        ]

        # Route tables: disassociate first.
        rt_resp = client.describe_route_tables(Filters=owner_only)
        for rt in rt_resp.get("RouteTables", []):
            rt_id = rt.get("RouteTableId", "")
            for assoc in rt.get("Associations", []):
                assoc_id = assoc.get("RouteTableAssociationId", "")
                if assoc.get("Main", False) is True:
                    continue
                if len(assoc_id) > 0:
                    try:
                        client.disassociate_route_table(
                            AssociationId=assoc_id
                        )
                    except Exception:
                        # Best-effort disassociate; the association may already be gone, and the
                        # route table delete below is attempted either way.
                        pass
            try:
                client.delete_route_table(RouteTableId=rt_id)
            except Exception:
                # Best-effort teardown; a failed delete must not stop the remaining
                # resources of the run from being torn down.
                pass

        subnet_resp = client.describe_subnets(Filters=owner_only)
        for subnet in subnet_resp.get("Subnets", []):
            sub_id = subnet.get("SubnetId", "")
            try:
                client.delete_subnet(SubnetId=sub_id)
                deleted.append(sub_id)
            except Exception:
                # Best-effort teardown sweep; a resource that fails to delete is left out
                # of the returned list and the sweep continues with the remaining resources.
                pass

        rtnval = deleted
        return rtnval

    def list_owned(self, *, run_id: str) -> List[ProvisionedResource]:
        """
            Return all owned subnets for the run as ProvisionedResources.

            :param run_id: Run identifier.

            :returns: List of ProvisionedResource entries.
        """
        client = self._ec2()
        owner_only = [
            {"Name": "tag:ccai:owned-by",
             "Values": ["codecraftai-provisioning"]},
            {"Name": "tag:ccai:owner", "Values": [run_id]},
        ]
        response = client.describe_subnets(Filters=owner_only)
        out: List[ProvisionedResource] = []
        for subnet in response.get("Subnets", []):
            tag_flat = tag_dict_from_aws(aws_tags=subnet.get("Tags", []))
            name = tag_flat.get(RESOURCE_NAME_TAG_KEY, "")
            if len(name) == 0:
                continue
            attributes: Dict[str, Any] = {}
            attributes["subnet_id"] = subnet.get("SubnetId", "")
            attributes["vpc_id"] = subnet.get("VpcId", "")
            attributes["cidr"] = subnet.get("CidrBlock", "")
            attributes["zone"] = subnet.get("AvailabilityZone", "")
            entry = ProvisionedResource(
                kind=self.KIND, name=name,
                venue_id=subnet.get("SubnetId", ""),
                attributes=attributes,
                tags=from_aws(aws_tags=subnet.get("Tags", [])),
            )
            out.append(entry)
        rtnval = out
        return rtnval
