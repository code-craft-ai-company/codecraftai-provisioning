"""
    .. module:: cloudsecuritygroup
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Venue-neutral security group descriptor.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.restclient.base.schemaobject import SchemaObject
from automojo.restclient.base.schemafield import Field

from automojo.provisioning.model.cloud.validators import validate_name
from automojo.provisioning.model.cloud.cloudingressrule import CloudIngressRule
from automojo.provisioning.model.cloud.cloudegressrule import CloudEgressRule


class CloudSecurityGroup(SchemaObject):
    """
        Venue-neutral security-group descriptor.

        Carries lists of ingress and egress rules that reference the same parent
        CloudNetwork.  Rule shape is checked at construction; the lifecycle
        validator confirms each rule's CIDRs / SG references resolve.
    """

    name = Field(str, required=True)
    network = Field(str, required=True)
    ingress_rules = Field(list, required=False, default=None)
    egress_rules = Field(list, required=False, default=None)
    tags = Field(list, required=False, default=None)

    def __init__(self, *, name: str, network: str,
                 ingress_rules: Optional[List[CloudIngressRule]] = None,
                 egress_rules: Optional[List[CloudEgressRule]] = None,
                 tags: Optional[List[Dict[str, str]]] = None) -> None:
        """
            Construct a CloudSecurityGroup.

            :param name: Security group name.
            :param network: Name of the parent CloudNetwork.
            :param ingress_rules: Optional list of ingress rules.
            :param egress_rules: Optional list of egress rules.
            :param tags: Optional list of single-entry tag dicts.

            :raises: SchemaValidationError
        """
        validate_name(value=name)
        validate_name(value=network)

        effective_ingress = ingress_rules if ingress_rules is not None else []
        effective_egress = egress_rules if egress_rules is not None else []
        effective_tags = tags if tags is not None else []

        super().__init__(name=name, network=network,
                         ingress_rules=effective_ingress,
                         egress_rules=effective_egress, tags=effective_tags)
        return

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CloudSecurityGroup":
        """
            Construct a CloudSecurityGroup from a serialised payload.

            Promotes nested rule dicts to typed rule objects.

            :param data: The serialised payload.

            :returns: A CloudSecurityGroup instance.
        """
        if not isinstance(data, dict):
            return data  # type: ignore

        ingress_payload = data.get("ingress_rules", None)
        egress_payload = data.get("egress_rules", None)

        promoted_ingress: List[CloudIngressRule] = []
        if ingress_payload is not None:
            for entry in ingress_payload:
                if isinstance(entry, CloudIngressRule):
                    promoted_ingress.append(entry)
                else:
                    promoted_ingress.append(CloudIngressRule.from_dict(entry))

        promoted_egress: List[CloudEgressRule] = []
        if egress_payload is not None:
            for entry in egress_payload:
                if isinstance(entry, CloudEgressRule):
                    promoted_egress.append(entry)
                else:
                    promoted_egress.append(CloudEgressRule.from_dict(entry))

        rtnval = cls(name=data["name"], network=data["network"],
                     ingress_rules=promoted_ingress,
                     egress_rules=promoted_egress,
                     tags=data.get("tags", None))
        return rtnval
