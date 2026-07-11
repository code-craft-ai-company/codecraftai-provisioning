"""
    .. module:: nsgmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Azure Network Security Group manager (NSG + security rules).

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from ccai.provisioning.model.cloud.cloudsecuritygroup import (
    CloudSecurityGroup
)
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.venues.azure.azureidempotency import (
    belongs_to_run, get_or_none
)
from ccai.provisioning.venues.azure.azuresessionfactory import (
    AzureSessionFactory
)
from ccai.provisioning.venues.azure.azuretagging import (
    azure_tags_for, from_azure
)
from ccai.provisioning.venues.azure.azuretask import resolve_poller


# NSG rule priorities are auto-assigned starting here, stepping by 10.
_PRIORITY_BASE = 1000
_PRIORITY_STEP = 10

# Neutral protocol → Azure NSG protocol.
_PROTOCOL_MAP: Dict[str, str] = {
    "tcp": "Tcp",
    "udp": "Udp",
    "icmp": "Icmp",
    "all": "*",
}


def _protocol_to_azure(*, protocol: str) -> str:
    """
        Map a neutral protocol string to the Azure NSG protocol form.

        :param protocol: Neutral protocol (tcp, udp, icmp, all).

        :returns: Azure NSG protocol string.
    """
    rtnval = _PROTOCOL_MAP.get(protocol, "*")
    return rtnval


def _port_range(*, protocol: str, from_port: int, to_port: int) -> str:
    """
        Build the Azure ``*_port_range`` string for a rule.

        :param protocol: Neutral protocol string.
        :param from_port: Lower port bound.
        :param to_port: Upper port bound.

        :returns: A port-range string ("*" for protocol all).
    """
    if protocol == "all":
        rtnval = "*"
        return rtnval
    if from_port == to_port:
        rtnval = str(from_port)
        return rtnval
    rtnval = "{}-{}".format(from_port, to_port)
    return rtnval


def _ingress_rule_to_azure(*, rule: Any, name: str, priority: int
                           ) -> Dict[str, Any]:
    """
        Translate a CloudIngressRule to an Azure security-rule dict.

        :param rule: A CloudIngressRule.
        :param name: NSG security-rule name.
        :param priority: Auto-assigned rule priority.

        :returns: A dict in the Azure SecurityRule schema.
    """
    cidrs = list(rule.source_cidrs) if rule.source_cidrs is not None else []
    out: Dict[str, Any] = {}
    out["name"] = name
    out["protocol"] = _protocol_to_azure(protocol=rule.protocol)
    out["source_port_range"] = "*"
    out["destination_port_range"] = _port_range(
        protocol=rule.protocol, from_port=rule.from_port,
        to_port=rule.to_port
    )
    if len(cidrs) == 1:
        out["source_address_prefix"] = cidrs[0]
    else:
        out["source_address_prefixes"] = cidrs
    out["destination_address_prefix"] = "*"
    out["access"] = "Allow"
    out["priority"] = priority
    out["direction"] = "Inbound"
    rtnval = out
    return rtnval


def _egress_rule_to_azure(*, rule: Any, name: str, priority: int
                          ) -> Dict[str, Any]:
    """
        Translate a CloudEgressRule to an Azure security-rule dict.

        :param rule: A CloudEgressRule.
        :param name: NSG security-rule name.
        :param priority: Auto-assigned rule priority.

        :returns: A dict in the Azure SecurityRule schema.
    """
    cidrs = list(rule.dest_cidrs) if rule.dest_cidrs is not None else []
    out: Dict[str, Any] = {}
    out["name"] = name
    out["protocol"] = _protocol_to_azure(protocol=rule.protocol)
    out["source_port_range"] = "*"
    out["destination_port_range"] = _port_range(
        protocol=rule.protocol, from_port=rule.from_port,
        to_port=rule.to_port
    )
    out["source_address_prefix"] = "*"
    if len(cidrs) == 1:
        out["destination_address_prefix"] = cidrs[0]
    else:
        out["destination_address_prefixes"] = cidrs
    out["access"] = "Allow"
    out["priority"] = priority
    out["direction"] = "Outbound"
    rtnval = out
    return rtnval


def build_security_rules(*, desired: CloudSecurityGroup
                         ) -> List[Dict[str, Any]]:
    """
        Build the ordered Azure security-rule list for a CloudSecurityGroup.

        Priorities are auto-assigned starting at 1000, ascending; inbound
        rules first, then outbound.

        :param desired: Desired CloudSecurityGroup.

        :returns: A list of Azure SecurityRule dicts.
    """
    rules: List[Dict[str, Any]] = []
    priority = _PRIORITY_BASE

    ingress = desired.ingress_rules if desired.ingress_rules is not None else []
    for index, rule in enumerate(ingress):
        rule_name = "{}-in-{}".format(desired.name, index)
        rules.append(_ingress_rule_to_azure(rule=rule, name=rule_name,
                                            priority=priority))
        priority = priority + _PRIORITY_STEP

    priority = _PRIORITY_BASE
    egress = desired.egress_rules if desired.egress_rules is not None else []
    for index, rule in enumerate(egress):
        rule_name = "{}-out-{}".format(desired.name, index)
        rules.append(_egress_rule_to_azure(rule=rule, name=rule_name,
                                           priority=priority))
        priority = priority + _PRIORITY_STEP

    rtnval = rules
    return rtnval



from azure.core.exceptions import ResourceNotFoundError
from ccai.xmodules.xlogging.enhancedloggers import getEnhancedLogger

logger = getEnhancedLogger()

class NsgManager:
    """
        Manager for Azure Network Security Groups.

        An NSG is created with its inbound/outbound security rules attached;
        priorities are auto-assigned.  Rule drift is detected as a rule-count
        / priority mismatch and reported as an UPDATE intent.
    """

    KIND: str = "sg"

    def __init__(self, *, session_factory: AzureSessionFactory) -> None:
        """
            Construct an NsgManager.

            :param session_factory: AzureSessionFactory.
        """
        self._session_factory: AzureSessionFactory = session_factory
        return

    def _network(self) -> Any:
        """
            Return the NetworkManagementClient.

            :returns: A NetworkManagementClient.
        """
        rtnval = self._session_factory.network_client()
        return rtnval

    def find(self, *, resource_group: str,
             name: str) -> Optional[Any]:
        """
            Find an existing NSG by name.

            :param resource_group: ResourceGroup name.
            :param name: Neutral security-group name.

            :returns: The NetworkSecurityGroup object, or None.
        """
        client = self._network()
        rtnval = get_or_none(getter=client.network_security_groups.get,
                             resource_group_name=resource_group,
                             network_security_group_name=name)
        return rtnval

    def matches(self, *, existing: Any,
                desired: CloudSecurityGroup) -> bool:
        """
            Compare an existing NSG to the desired CloudSecurityGroup.

            :param existing: The live NetworkSecurityGroup object.
            :param desired: Desired CloudSecurityGroup.

            :returns: True when the rule count matches.
        """
        desired_rules = build_security_rules(desired=desired)
        live_rules = getattr(existing, "security_rules", None) or []
        rtnval = len(desired_rules) == len(list(live_rules))
        return rtnval

    def ensure(self, *, desired: CloudSecurityGroup, resource_group: str,
               location: str, run_id: str,
               default_tags: List[Dict[str, str]],
               aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for an NSG.

            :param desired: Desired CloudSecurityGroup.
            :param resource_group: ResourceGroup name.
            :param location: Azure location.
            :param run_id: Run identifier (used for owner tagging).
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the NSG.
        """
        client = self._network()
        existing = self.find(resource_group=resource_group,
                             name=desired.name)
        rules = build_security_rules(desired=desired)

        if existing is None:
            tags = azure_tags_for(run_id=run_id, resource_name=desired.name,
                                  resource_kind=self.KIND,
                                  extra=dict(desired.tags),
                                  defaults=default_tags)
            params: Dict[str, Any] = {
                "location": location,
                "security_rules": rules,
                "tags": tags,
            }
            poller = client.network_security_groups.begin_create_or_update(
                resource_group_name=resource_group,
                network_security_group_name=desired.name,
                parameters=params,
            )
            existing = resolve_poller(poller=poller, aspects=aspects,
                                      description="create nsg {}".format(
                                          desired.name
                                      ))

        attributes: Dict[str, Any] = {}
        attributes["nsg_name"] = desired.name
        attributes["resource_group"] = resource_group
        attributes["rule_count"] = len(rules)

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name,
            venue_id=getattr(existing, "id", desired.name),
            attributes=attributes,
            tags=from_azure(azure_tags=getattr(existing, "tags", None)),
        )
        return rtnval

    def destroy(self, *, resource_group: str,
                run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned NSG in the ResourceGroup for the run.

            :param resource_group: ResourceGroup name.
            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of destroyed NSG names.
        """
        client = self._network()
        deleted: List[str] = []
        try:
            listing = list(client.network_security_groups.list(
                resource_group_name=resource_group
            ))
        except ResourceNotFoundError:
            # Resource group / listing target absent -> nothing owned.
            rtnval = deleted
            return rtnval
        except Exception as xcpt:
            # Do NOT mask a transient/auth/list failure as 'nothing owned';
            # that under-reports ownership and corrupts inventory/destroy.
            logger.warning("Failed to list Azure %s in resource_group=%s: %s" % (self.KIND, resource_group, xcpt))
            raise

        for nsg in listing:
            if not belongs_to_run(azure_tags=getattr(nsg, "tags", None),
                                  run_id=run_id):
                continue
            nsg_name = getattr(nsg, "name", "")
            try:
                client.network_security_groups.begin_delete(
                    resource_group_name=resource_group,
                    network_security_group_name=nsg_name,
                )
                deleted.append(nsg_name)
            except Exception:
                pass

        rtnval = deleted
        return rtnval

    def list_owned(self, *, resource_group: str,
                   run_id: str) -> List[ProvisionedResource]:
        """
            Return all owned NSGs in the ResourceGroup for the run.

            :param resource_group: ResourceGroup name.
            :param run_id: Run identifier.

            :returns: List of ProvisionedResource entries.
        """
        client = self._network()
        out: List[ProvisionedResource] = []
        try:
            listing = list(client.network_security_groups.list(
                resource_group_name=resource_group
            ))
        except ResourceNotFoundError:
            # Resource group / listing target absent -> nothing owned.
            rtnval = out
            return rtnval
        except Exception as xcpt:
            # Do NOT mask a transient/auth/list failure as 'nothing owned';
            # that under-reports ownership and corrupts inventory/destroy.
            logger.warning("Failed to list Azure %s in resource_group=%s: %s" % (self.KIND, resource_group, xcpt))
            raise

        for nsg in listing:
            live_tags = getattr(nsg, "tags", None)
            if not belongs_to_run(azure_tags=live_tags, run_id=run_id):
                continue
            attributes: Dict[str, Any] = {}
            attributes["nsg_name"] = getattr(nsg, "name", "")
            attributes["resource_group"] = resource_group
            out.append(ProvisionedResource(
                kind=self.KIND, name=getattr(nsg, "name", ""),
                venue_id=getattr(nsg, "id", getattr(nsg, "name", "x")),
                attributes=attributes,
                tags=from_azure(azure_tags=live_tags),
            ))

        rtnval = out
        return rtnval
