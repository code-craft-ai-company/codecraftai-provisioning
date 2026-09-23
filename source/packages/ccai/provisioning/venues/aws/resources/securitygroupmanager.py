"""
    .. module:: securitygroupmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: AWS SecurityGroup manager for the AWS venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional, Tuple

from ccai.restclient.aws.awserror import ClientError

from ccai.provisioning.model.cloud.cloudsecuritygroup import (
    CloudSecurityGroup
)
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


# EC2 creates every new VPC security group with this allow-all IPv4 egress rule.
_DEFAULT_EGRESS_PROTOCOL = "-1"
_DEFAULT_EGRESS_CIDR = "0.0.0.0/0"


def _split_default_egress(*, egress_aws: List[Dict[str, Any]]
                          ) -> Tuple[List[Dict[str, Any]],
                                     Optional[Dict[str, Any]]]:
    """
        Separate the allow-all egress rule EC2 creates with every new group
        from the rest of the requested egress permissions.

        EC2 authorizes a batch atomically: one ``InvalidPermission.Duplicate``
        rejects every permission in the call.  Keeping the default rule out of
        the main batch stops that one expected duplicate from dropping the
        other requested rules.

        :param egress_aws: Egress permissions in the AWS IpPermissions schema.

        :returns: A ``(remaining, default_rule)`` pair.  ``default_rule`` is
                  None when the request does not include the allow-all rule.
    """
    remaining: List[Dict[str, Any]] = []
    default_rule: Optional[Dict[str, Any]] = None

    for permission in egress_aws:
        if permission.get("IpProtocol", "") != _DEFAULT_EGRESS_PROTOCOL:
            remaining.append(permission)
            continue

        found_default = False
        other_ranges: List[Dict[str, Any]] = []
        for ip_range in permission.get("IpRanges", []):
            if ip_range.get("CidrIp", "") == _DEFAULT_EGRESS_CIDR:
                found_default = True
            else:
                other_ranges.append(ip_range)

        if found_default is False:
            remaining.append(permission)
            continue

        default_rule = {
            "IpProtocol": _DEFAULT_EGRESS_PROTOCOL,
            "IpRanges": [{"CidrIp": _DEFAULT_EGRESS_CIDR}],
        }
        if len(other_ranges) > 0:
            trimmed = dict(permission)
            trimmed["IpRanges"] = other_ranges
            remaining.append(trimmed)

    rtnval = (remaining, default_rule)
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
                Description="ccai SG {}".format(desired.name),
                VpcId=vpc_id,
                TagSpecifications=tag_specs,
            )
            sg_id = created.get("GroupId", "")

            if len(ingress_aws) > 0:
                # The group was created a moment ago with no inbound rules, so
                # there is no duplicate to tolerate; any failure is real.
                client.authorize_security_group_ingress(
                    GroupId=sg_id, IpPermissions=ingress_aws
                )
            if len(egress_aws) > 0:
                remaining_egress, default_egress = _split_default_egress(
                    egress_aws=egress_aws
                )
                if len(remaining_egress) > 0:
                    client.authorize_security_group_egress(
                        GroupId=sg_id, IpPermissions=remaining_egress
                    )
                if default_egress is not None:
                    try:
                        client.authorize_security_group_egress(
                            GroupId=sg_id, IpPermissions=[default_egress]
                        )
                    except ClientError as xcpt:
                        # EC2 already gave the new group this allow-all egress
                        # rule, so it answers InvalidPermission.Duplicate and
                        # the rule is in the requested state.  Any other
                        # error is real.
                        if xcpt.code != "InvalidPermission.Duplicate":
                            raise
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
            {"Name": "tag:ccai:owned-by",
             "Values": ["codecraftai-provisioning"]},
            {"Name": "tag:ccai:owner", "Values": [run_id]},
        ]
        response = client.describe_security_groups(Filters=owner_only)
        for group in response.get("SecurityGroups", []):
            gid = group.get("GroupId", "")
            try:
                client.delete_security_group(GroupId=gid)
                deleted.append(gid)
            except Exception:
                # Best-effort teardown sweep; a resource that fails to delete is left out
                # of the returned list and the sweep continues with the remaining resources.
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
            {"Name": "tag:ccai:owned-by",
             "Values": ["codecraftai-provisioning"]},
            {"Name": "tag:ccai:owner", "Values": [run_id]},
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
