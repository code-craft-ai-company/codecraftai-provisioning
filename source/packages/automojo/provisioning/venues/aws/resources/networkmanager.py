"""
    .. module:: networkmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: AWS VPC + IGW + RouteTable manager for the AWS venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.provisioning.model.cloud.cloudnetwork import CloudNetwork
from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.venues.aws.awsboto3sessionfactory import (
    AwsBoto3SessionFactory
)
from automojo.provisioning.venues.aws.awsidempotency import (
    is_owned, owner_filters, tag_dict_from_aws
)
from automojo.provisioning.venues.aws.awstagging import (
    base_resource_tags, tag_specifications, RESOURCE_NAME_TAG_KEY
)


class NetworkManager:
    """
        Manager for AWS VPCs.

        VPCs are tagged with the venue owner/run/name tag triple.  Idempotent
        ``ensure`` is done by tag lookup; an existing tagged VPC is reused.
    """

    KIND: str = "network"
    RESOURCE_TYPE: str = "vpc"

    def __init__(self, *, session_factory: AwsBoto3SessionFactory) -> None:
        """
            Construct a NetworkManager.

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
            Find an existing owned VPC by run+name tags.

            :param run_id: Run identifier.
            :param name: Neutral network name.

            :returns: The describe_vpcs ``Vpc`` dict, or None.
        """
        client = self._ec2()
        filters = owner_filters(run_id=run_id, resource_name=name)
        response = client.describe_vpcs(Filters=filters)
        vpcs = response.get("Vpcs", [])
        if len(vpcs) == 0:
            rtnval: Optional[Dict[str, Any]] = None
            return rtnval
        rtnval = vpcs[0]
        return rtnval

    def matches(self, *, existing: Dict[str, Any],
                desired: CloudNetwork) -> bool:
        """
            Compare an existing VPC to the desired CloudNetwork.

            :param existing: AWS describe_vpcs entry.
            :param desired: Desired CloudNetwork.

            :returns: True when the CIDR matches.
        """
        cidr_match = existing.get("CidrBlock", None) == desired.cidr
        rtnval = cidr_match
        return rtnval

    def ensure(self, *, desired: CloudNetwork, run_id: str,
               default_tags: List[Dict[str, str]],
               aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for a VPC plus its IGW.

            :param desired: Desired CloudNetwork.
            :param run_id: Run identifier (used for owner tagging).
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the VPC.
        """
        client = self._ec2()
        existing = self.find(run_id=run_id, name=desired.name)

        if existing is None:
            neutral_tags = base_resource_tags(
                run_id=run_id, resource_name=desired.name,
                resource_kind=self.KIND, extra=list(desired.tags),
                defaults=default_tags,
            )
            tag_specs = tag_specifications(
                resource_type=self.RESOURCE_TYPE, neutral_tags=neutral_tags
            )
            created = client.create_vpc(
                CidrBlock=desired.cidr,
                TagSpecifications=tag_specs,
            )
            vpc = created.get("Vpc", {})
            existing = vpc

        vpc_id = existing.get("VpcId", "")

        # Idempotently ensure an Internet Gateway + attachment.
        igw_id = self._ensure_igw(run_id=run_id, network_name=desired.name,
                                  vpc_id=vpc_id, default_tags=default_tags)

        # Build the attributes payload.
        attributes: Dict[str, Any] = {}
        attributes["vpc_id"] = vpc_id
        attributes["cidr"] = existing.get("CidrBlock", desired.cidr)
        attributes["region"] = desired.region
        attributes["igw_id"] = igw_id

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=vpc_id,
            attributes=attributes,
            tags=self._neutral_tag_list_from_existing(existing=existing),
        )
        return rtnval

    def _ensure_igw(self, *, run_id: str, network_name: str, vpc_id: str,
                    default_tags: List[Dict[str, str]]) -> str:
        """
            Create or reuse an Internet Gateway attached to the VPC.

            :param run_id: Run identifier.
            :param network_name: Neutral network name.
            :param vpc_id: AWS VPC id to attach to.
            :param default_tags: Venue default tags.

            :returns: The Internet Gateway id.
        """
        client = self._ec2()
        igw_name = "{}-igw".format(network_name)
        filters = owner_filters(run_id=run_id, resource_name=igw_name)
        response = client.describe_internet_gateways(Filters=filters)
        gateways = response.get("InternetGateways", [])
        if len(gateways) > 0:
            existing_igw = gateways[0]
            igw_id = existing_igw.get("InternetGatewayId", "")
            attachments = existing_igw.get("Attachments", [])
            attached = False
            for entry in attachments:
                if entry.get("VpcId", "") == vpc_id:
                    attached = True
            if attached is False:
                client.attach_internet_gateway(InternetGatewayId=igw_id,
                                               VpcId=vpc_id)
            rtnval = igw_id
            return rtnval

        neutral_tags = base_resource_tags(
            run_id=run_id, resource_name=igw_name,
            resource_kind="internet_gateway", defaults=default_tags,
        )
        tag_specs = tag_specifications(
            resource_type="internet-gateway", neutral_tags=neutral_tags
        )
        created = client.create_internet_gateway(TagSpecifications=tag_specs)
        igw_id = created.get("InternetGateway", {}).get("InternetGatewayId",
                                                        "")
        client.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
        rtnval = igw_id
        return rtnval

    def destroy(self, *, run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned VPC + IGW for the run.

            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of destroyed VPC ids.
        """
        client = self._ec2()
        deleted: List[str] = []

        # Detach + delete IGWs first.
        owner_only = [
            {"Name": "tag:automojo:owned-by",
             "Values": ["automojo-provisioning"]},
            {"Name": "tag:automojo:owner", "Values": [run_id]},
        ]
        igw_resp = client.describe_internet_gateways(Filters=owner_only)
        for igw in igw_resp.get("InternetGateways", []):
            igw_id = igw.get("InternetGatewayId", "")
            for entry in igw.get("Attachments", []):
                attached_vpc = entry.get("VpcId", "")
                if len(attached_vpc) > 0:
                    try:
                        client.detach_internet_gateway(
                            InternetGatewayId=igw_id, VpcId=attached_vpc
                        )
                    except Exception:
                        pass
            try:
                client.delete_internet_gateway(InternetGatewayId=igw_id)
            except Exception:
                pass

        vpc_resp = client.describe_vpcs(Filters=owner_only)
        for vpc in vpc_resp.get("Vpcs", []):
            vpc_id = vpc.get("VpcId", "")
            try:
                client.delete_vpc(VpcId=vpc_id)
                deleted.append(vpc_id)
            except Exception:
                pass

        rtnval = deleted
        return rtnval

    def list_owned(self, *, run_id: str) -> List[ProvisionedResource]:
        """
            Return all owned VPCs for the run as ProvisionedResources.

            :param run_id: Run identifier.

            :returns: List of ProvisionedResource entries.
        """
        client = self._ec2()
        owner_only = [
            {"Name": "tag:automojo:owned-by",
             "Values": ["automojo-provisioning"]},
            {"Name": "tag:automojo:owner", "Values": [run_id]},
        ]
        response = client.describe_vpcs(Filters=owner_only)
        out: List[ProvisionedResource] = []
        for vpc in response.get("Vpcs", []):
            tag_flat = tag_dict_from_aws(aws_tags=vpc.get("Tags", []))
            name = tag_flat.get(RESOURCE_NAME_TAG_KEY, "")
            if len(name) == 0:
                continue
            attributes: Dict[str, Any] = {}
            attributes["vpc_id"] = vpc.get("VpcId", "")
            attributes["cidr"] = vpc.get("CidrBlock", "")
            entry = ProvisionedResource(
                kind=self.KIND, name=name,
                venue_id=vpc.get("VpcId", ""),
                attributes=attributes,
                tags=self._neutral_tag_list_from_existing(existing=vpc),
            )
            out.append(entry)
        rtnval = out
        return rtnval

    @staticmethod
    def _neutral_tag_list_from_existing(*, existing: Dict[str, Any]
                                        ) -> List[Dict[str, str]]:
        """
            Reconstruct neutral tags from an AWS resource describe entry.

            :param existing: AWS describe entry.

            :returns: A list of single-entry neutral tag dicts.
        """
        from automojo.provisioning.venues.aws.awstagging import from_aws
        rtnval = from_aws(aws_tags=existing.get("Tags", []))
        return rtnval
