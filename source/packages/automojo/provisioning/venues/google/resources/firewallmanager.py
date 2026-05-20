"""
    .. module:: firewallmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: GCP firewall rule manager for the Google venue.

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
from automojo.provisioning.venues.google.gcpsessionfactory import (
    GcpSessionFactory, SERVICE_COMPUTE
)
from automojo.provisioning.venues.google.gcpidempotency import (
    belongs_to_run
)
from automojo.provisioning.venues.google.gcptagging import (
    base_resource_labels, from_labels, RESOURCE_NAME_LABEL_KEY
)


def _ingress_rule_to_firewall_allowed(rule: Any) -> Dict[str, Any]:
    """
        Translate a CloudIngressRule to a GCP firewall ``allowed`` entry.

        :param rule: A CloudIngressRule.

        :returns: A dict in the GCP firewall ``allowed`` schema.
    """
    protocol = rule.protocol if rule.protocol != "all" else "all"
    out: Dict[str, Any] = {"IPProtocol": protocol}
    if rule.protocol != "all":
        out["ports"] = ["{}-{}".format(rule.from_port, rule.to_port)]
    rtnval = out
    return rtnval


class FirewallManager:
    """
        Manager for GCP firewall rules.

        GCP firewall is network-scoped, not instance-scoped: a neutral
        :class:`CloudSecurityGroup` is realised as one firewall rule per
        ingress entry, all targeting the parent VPC network.  Source CIDRs
        come from each rule's ``source_cidrs``.
    """

    KIND: str = "firewall"

    def __init__(self, *, session_factory: GcpSessionFactory) -> None:
        """
            Construct a FirewallManager.

            :param session_factory: GcpSessionFactory.
        """
        self._session_factory: GcpSessionFactory = session_factory
        return

    def _client(self) -> Any:
        """
            Return the compute ``firewalls`` sub-client.

            :returns: The firewalls sub-client.
        """
        compute = self._session_factory.client(service_name=SERVICE_COMPUTE)
        rtnval = compute["firewalls"]
        return rtnval

    def _gcp_name(self, *, run_id: str, sg_name: str, index: int) -> str:
        """
            Build the GCP-side firewall rule name.

            :param run_id: Run identifier.
            :param sg_name: Neutral security group name.
            :param index: Ingress rule index.

            :returns: A GCP-conformant firewall rule name.
        """
        rtnval = "automojo-{}-{}-{}".format(run_id, sg_name, index).lower()
        return rtnval

    def find(self, *, run_id: str, name: str) -> Optional[Dict[str, Any]]:
        """
            Find an existing owned firewall rule by run+name labels.

            :param run_id: Run identifier.
            :param name: Neutral security group name.

            :returns: The first firewall rule resource dict, or None.
        """
        for entry in self.list_raw(run_id=run_id):
            labels = entry.get("labels", {})
            if labels.get(RESOURCE_NAME_LABEL_KEY, "") == name:
                rtnval: Optional[Dict[str, Any]] = entry
                return rtnval
        rtnval = None
        return rtnval

    def ensure(self, *, desired: CloudSecurityGroup, run_id: str,
               network_self_link: str,
               default_tags: List[Dict[str, str]],
               aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for a security group's firewall.

            One firewall rule is created per ingress entry.

            :param desired: Desired CloudSecurityGroup.
            :param run_id: Run identifier.
            :param network_self_link: Parent VPC network self-link.
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the firewall rule set.
        """
        client = self._client()
        project = self._session_factory.project

        ingress_rules = (
            desired.ingress_rules if desired.ingress_rules is not None else []
        )
        rule_names: List[str] = []
        for index, rule in enumerate(ingress_rules):
            gcp_name = self._gcp_name(run_id=run_id, sg_name=desired.name,
                                      index=index)
            rule_names.append(gcp_name)
            existing = client.get(project=project, firewall=gcp_name)
            if existing is not None and belongs_to_run(
                    labels=existing.get("labels", {}), run_id=run_id):
                continue

            labels = base_resource_labels(
                run_id=run_id, resource_name=desired.name,
                resource_kind=self.KIND, extra=list(desired.tags),
                defaults=default_tags,
            )
            source_cidrs = (
                list(rule.source_cidrs)
                if rule.source_cidrs is not None else []
            )
            body: Dict[str, Any] = {
                "name": gcp_name,
                "network": network_self_link,
                "direction": "INGRESS",
                "source_ranges": source_cidrs,
                "allowed": [_ingress_rule_to_firewall_allowed(rule)],
                "labels": labels,
            }
            client.insert(project=project, firewall_resource=body)

        first_name = rule_names[0] if len(rule_names) > 0 else (
            "automojo-{}-{}-0".format(run_id, desired.name).lower()
        )
        attributes: Dict[str, Any] = {}
        attributes["firewall_names"] = rule_names
        attributes["network"] = network_self_link

        existing_first = client.get(project=project, firewall=first_name)
        tag_source = (
            existing_first.get("labels", {})
            if existing_first is not None else {}
        )

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=first_name,
            attributes=attributes,
            tags=from_labels(labels=tag_source),
        )
        return rtnval

    def destroy(self, *, run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned firewall rule for the run.

            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of destroyed firewall rule names.
        """
        client = self._client()
        project = self._session_factory.project
        deleted: List[str] = []
        for entry in self.list_raw(run_id=run_id):
            gcp_name = entry.get("name", "")
            if len(gcp_name) == 0:
                continue
            try:
                client.delete(project=project, firewall=gcp_name)
                deleted.append(gcp_name)
            except Exception:
                pass
        rtnval = deleted
        return rtnval

    def list_raw(self, *, run_id: str) -> List[Dict[str, Any]]:
        """
            Return raw owned firewall rule resource dicts for the run.

            :param run_id: Run identifier.

            :returns: List of firewall rule resource dicts.
        """
        client = self._client()
        project = self._session_factory.project
        out: List[Dict[str, Any]] = []
        for entry in client.list(project=project):
            if belongs_to_run(labels=entry.get("labels", {}),
                              run_id=run_id):
                out.append(entry)
        rtnval = out
        return rtnval

    def list_owned(self, *, run_id: str) -> List[ProvisionedResource]:
        """
            Return all owned firewall rules for the run.

            :param run_id: Run identifier.

            :returns: List of ProvisionedResource entries (one per rule).
        """
        out: List[ProvisionedResource] = []
        for entry in self.list_raw(run_id=run_id):
            labels = entry.get("labels", {})
            name = labels.get(RESOURCE_NAME_LABEL_KEY, "")
            if len(name) == 0:
                continue
            attributes: Dict[str, Any] = {}
            attributes["gcp_name"] = entry.get("name", "")
            resource = ProvisionedResource(
                kind=self.KIND, name=name,
                venue_id=entry.get("name", ""),
                attributes=attributes,
                tags=from_labels(labels=labels),
            )
            out.append(resource)
        rtnval = out
        return rtnval
