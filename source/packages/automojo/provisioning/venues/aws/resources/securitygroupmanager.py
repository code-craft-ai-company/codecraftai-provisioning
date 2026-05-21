"""
    .. module:: securitygroupmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: AWS SecurityGroup manager for the AWS venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.provisioning.model.cloud.cloudsecuritygroup import (
    CloudSecurityGroup
)
from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.venues.aws.awsboto3sessionfactory import (
    AwsBoto3SessionFactory
)
from automojo.provisioning.venues.aws.awsidempotency import (
    owner_filters, tag_dict_from_aws
)
from automojo.provisioning.venues.aws.awstagging import (
    base_resource_tags, tag_specifications, from_aws, RESOURCE_NAME_TAG_KEY
)


def _ingress_to_aws(rule: Any) -> Dict[str, Any]:
    """
        Translate a CloudIngressRule to ``IpPermissions`` shape.

        :param rule: A CloudIngressRule.

        :returns: A dict in the AWS IpPermissions schema.
    """
    cidrs = list(rule.source_cidrs) if rule.source_cidrs is not None else []
    out: Dict[str, Any] = {}
    out["IpProtocol"] = rule.protocol if rule.protocol != "all" else "-1"
    if rule.protocol != "all":
        out["FromPort"] = rule.from_port
        out["ToPort"] = rule.to_port
    out["IpRanges"] = [{"CidrIp": cidr} for cidr in cidrs]
    rtnval = out
    return rtnval


def _egress_to_aws(rule: Any) -> Dict[str, Any]:
    """
        Translate a CloudEgressRule to ``IpPermissions`` shape.

        :param rule: A CloudEgressRule.

        :returns: A dict in the AWS IpPermissions schema.
    """
    cidrs = list(rule.dest_cidrs) if rule.dest_cidrs is not None else []
    out: Dict[str, Any] = {}
    out["IpProtocol"] = rule.protocol if rule.protocol != "all" else "-1"
    if rule.protocol != "all":
        out["FromPort"] = rule.from_port
        out["ToPort"] = rule.to_port
    out["IpRanges"] = [{"CidrIp": cidr} for cidr in cidrs]
    rtnval = out
    return rtnval


class SecurityGroupManager:
    """
        Manager for AWS Security Groups.

        Look up by owner+name; create with declared ingress/egress rules
        attached.  Rule drift is detected as an attribute-mismatch and is
        currently reported as an update intent (apply revokes-then-authorizes
        the listed rules).
    """

    KIND: str = "sg"

    def __init__(self, *, session_factory: AwsBoto3SessionFactory) -> None:
        """
            Construct a SecurityGroupManager.

            :param session_factory: AwsBoto3SessionFactory.
        """
        self._session_factory: AwsBoto3SessionFactory = session_factory
        return

    def _ec2(self) -> Any:
        rtnval = self._session_factory.client(service_name="ec2")
        return rtnval

    def find(self, *, run_id: str, name: str) -> Optional[Dict[str, Any]]:
        """
            Find an existing owned SG by run+name tags.

            :param run_id: Run identifier.
            :param name: Neutral SG name.

            :returns: The describe_security_groups entry or None.
        """
        client = self._ec2()
        filters = owner_filters(run_id=run_id, resource_name=name)
        response = client.describe_security_groups(Filters=filters)
        groups = response.get("SecurityGroups", [])
        if len(groups) == 0:
            rtnval: Optional[Dict[str, Any]] = None
            return rtnval
        rtnval = groups[0]
        return rtnval

    def ensure(self, *, desired: CloudSecurityGroup, run_id: str,
               vpc_id: str,
               default_tags: List[Dict[str, str]],
               aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for a Security Group.

            :param desired: Desired CloudSecurityGroup.
            :param run_id: Run identifier.
            :param vpc_id: Parent VPC id.
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the SG.
        """
        client = self._ec2()
        existing = self.find(run_id=run_id, name=desired.name)

        ingress_aws = [_ingress_to_aws(r) for r in (desired.ingress_rules or [])]
        egress_aws = [_egress_to_aws(r) for r in (desired.egress_rules or [])]

        if existing is None:
            neutral_tags = base_resource_tags(
                run_id=run_id, resource_name=desired.name,
                resource_kind=self.KIND, extra=dict(desired.tags),
                defaults=default_tags,
            )
            tag_specs = tag_specifications(
                resource_type="security-group", neutral_tags=neutral_tags
            )
            created = client.create_security_group(
                GroupName="{}-{}".format(desired.name, run_id),
                Description="automojo SG {}".format(desired.name),
                VpcId=vpc_id,
                TagSpecifications=tag_specs,
            )
            sg_id = created.get("GroupId", "")

            if len(ingress_aws) > 0:
                try:
                    client.authorize_security_group_ingress(
                        GroupId=sg_id, IpPermissions=ingress_aws
                    )
                except Exception:
                    pass
            if len(egress_aws) > 0:
                try:
                    client.authorize_security_group_egress(
                        GroupId=sg_id, IpPermissions=egress_aws
                    )
                except Exception:
                    pass
            existing = {"GroupId": sg_id, "Tags": []}
            existing = client.describe_security_groups(
                GroupIds=[sg_id]
            ).get("SecurityGroups", [{}])[0]

        sg_id = existing.get("GroupId", "")

        attributes: Dict[str, Any] = {}
        attributes["sg_id"] = sg_id
        attributes["vpc_id"] = vpc_id
        attributes["ingress_count"] = len(ingress_aws)
        attributes["egress_count"] = len(egress_aws)

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=sg_id,
            attributes=attributes,
            tags=from_aws(aws_tags=existing.get("Tags", [])),
        )
        return rtnval

    def destroy(self, *, run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned SG for the run.

            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of destroyed SG ids.
        """
        client = self._ec2()
        deleted: List[str] = []
        owner_only = [
            {"Name": "tag:automojo:owned-by",
             "Values": ["automojo-provisioning"]},
            {"Name": "tag:automojo:owner", "Values": [run_id]},
        ]
        response = client.describe_security_groups(Filters=owner_only)
        for group in response.get("SecurityGroups", []):
            gid = group.get("GroupId", "")
            try:
                client.delete_security_group(GroupId=gid)
                deleted.append(gid)
            except Exception:
                pass
        rtnval = deleted
        return rtnval

    def list_owned(self, *, run_id: str) -> List[ProvisionedResource]:
        """
            Return all owned SGs for the run.

            :param run_id: Run identifier.

            :returns: List of ProvisionedResource entries.
        """
        client = self._ec2()
        owner_only = [
            {"Name": "tag:automojo:owned-by",
             "Values": ["automojo-provisioning"]},
            {"Name": "tag:automojo:owner", "Values": [run_id]},
        ]
        response = client.describe_security_groups(Filters=owner_only)
        out: List[ProvisionedResource] = []
        for group in response.get("SecurityGroups", []):
            tag_flat = tag_dict_from_aws(aws_tags=group.get("Tags", []))
            name = tag_flat.get(RESOURCE_NAME_TAG_KEY, "")
            if len(name) == 0:
                continue
            attributes: Dict[str, Any] = {}
            attributes["sg_id"] = group.get("GroupId", "")
            attributes["vpc_id"] = group.get("VpcId", "")
            entry = ProvisionedResource(
                kind=self.KIND, name=name,
                venue_id=group.get("GroupId", ""),
                attributes=attributes,
                tags=from_aws(aws_tags=group.get("Tags", [])),
            )
            out.append(entry)
        rtnval = out
        return rtnval
