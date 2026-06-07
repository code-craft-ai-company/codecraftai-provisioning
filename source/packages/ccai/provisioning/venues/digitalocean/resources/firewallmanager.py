"""
    .. module:: firewallmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: DigitalOcean Cloud Firewall manager for the DigitalOcean venue.

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
from ccai.provisioning.venues.digitalocean.doclient import (
    DigitalOceanClient
)
from ccai.provisioning.venues.digitalocean.dotagtranslator import (
    base_resource_tags, from_do, to_do, to_flat, RESOURCE_NAME_TAG_KEY
)
from ccai.provisioning.venues.digitalocean.doidempotency import (
    matches_name, belongs_to_run
)


def _inbound_rules(*, group: CloudSecurityGroup) -> List[Dict[str, Any]]:
    """
        Translate neutral ingress rules to DigitalOcean inbound rules.

        :param group: The neutral CloudSecurityGroup.

        :returns: A list of DigitalOcean inbound-rule dicts.
    """
    rules: List[Dict[str, Any]] = []
    ingress = group.ingress_rules if group.ingress_rules is not None else []
    for rule in ingress:
        sources: Dict[str, Any] = {}
        cidrs = rule.source_cidrs if rule.source_cidrs is not None else []
        if len(cidrs) > 0:
            sources["addresses"] = list(cidrs)
        port_value = "{}".format(rule.from_port)
        if rule.from_port != rule.to_port:
            port_value = "{}-{}".format(rule.from_port, rule.to_port)
        rules.append({
            "protocol": rule.protocol,
            "ports": port_value,
            "sources": sources,
        })
    rtnval = rules
    return rtnval


def _outbound_rules(*, group: CloudSecurityGroup) -> List[Dict[str, Any]]:
    """
        Translate neutral egress rules to DigitalOcean outbound rules.

        :param group: The neutral CloudSecurityGroup.

        :returns: A list of DigitalOcean outbound-rule dicts.
    """
    rules: List[Dict[str, Any]] = []
    egress = group.egress_rules if group.egress_rules is not None else []
    for rule in egress:
        destinations: Dict[str, Any] = {}
        cidrs = rule.dest_cidrs if rule.dest_cidrs is not None else []
        if len(cidrs) > 0:
            destinations["addresses"] = list(cidrs)
        port_value = "{}".format(rule.from_port)
        if rule.from_port != rule.to_port:
            port_value = "{}-{}".format(rule.from_port, rule.to_port)
        rules.append({
            "protocol": rule.protocol,
            "ports": port_value,
            "destinations": destinations,
        })
    rtnval = rules
    return rtnval


class FirewallManager:
    """
        Manager for DigitalOcean Cloud Firewalls.

        Firewalls carry the venue owner / run / name tags natively as a
        string list.  Idempotent ``ensure`` reads firewalls filtered by the
        encoded run-id tag.
    """

    KIND: str = "sg"

    def __init__(self, *, client: DigitalOceanClient) -> None:
        """
            Construct a FirewallManager.

            :param client: DigitalOceanClient.
        """
        self._client: DigitalOceanClient = client
        return

    def _all_firewalls(self) -> List[Dict[str, Any]]:
        """
            List every firewall visible to the account.

            :returns: A list of firewall dicts.
        """
        response = self._client.firewalls.list()
        rtnval = list(response.get("firewalls", []))
        return rtnval

    def find(self, *, run_id: str, name: str) -> Optional[Dict[str, Any]]:
        """
            Find an existing owned firewall by run+name tags.

            :param run_id: Run identifier.
            :param name: Neutral security-group name.

            :returns: The firewall dict, or None.
        """
        for firewall in self._all_firewalls():
            do_tags = firewall.get("tags", [])
            if matches_name(do_tags=do_tags, run_id=run_id,
                            resource_name=name):
                rtnval: Optional[Dict[str, Any]] = firewall
                return rtnval
        rtnval = None
        return rtnval

    def matches(self, *, existing: Dict[str, Any],
                desired: CloudSecurityGroup) -> bool:
        """
            Compare an existing firewall to the desired CloudSecurityGroup.

            :param existing: DigitalOcean firewall dict.
            :param desired: Desired CloudSecurityGroup.

            :returns: True when the inbound + outbound rule sets match.
        """
        desired_in = _inbound_rules(group=desired)
        desired_out = _outbound_rules(group=desired)
        existing_in = existing.get("inbound_rules", []) or []
        existing_out = existing.get("outbound_rules", []) or []

        in_match = self._rules_equal(left=desired_in, right=existing_in,
                                     ref_key="sources")
        out_match = self._rules_equal(left=desired_out, right=existing_out,
                                      ref_key="destinations")
        rtnval = in_match and out_match
        return rtnval

    @staticmethod
    def _rules_equal(*, left: List[Dict[str, Any]],
                     right: List[Dict[str, Any]], ref_key: str) -> bool:
        """
            Compare two firewall rule lists for set equality.

            :param left: The desired rule list.
            :param right: The existing rule list.
            :param ref_key: Either ``sources`` or ``destinations``.

            :returns: True when the rule sets are equal.
        """
        def _norm(rule: Dict[str, Any]) -> tuple:
            ref = rule.get(ref_key, {}) or {}
            addresses = tuple(sorted(ref.get("addresses", []) or []))
            return (rule.get("protocol", ""), str(rule.get("ports", "")),
                    addresses)

        left_norm = sorted(_norm(rule) for rule in left)
        right_norm = sorted(_norm(rule) for rule in right)
        rtnval = left_norm == right_norm
        return rtnval

    def ensure(self, *, desired: CloudSecurityGroup, run_id: str,
               default_tags: List[Dict[str, str]],
               droplet_ids: Optional[List[int]] = None,
               aspects: Any = None) -> ProvisionedResource:
        """
            Match-then-act create-or-update for a Cloud Firewall.

            :param desired: Desired CloudSecurityGroup.
            :param run_id: Run identifier.
            :param default_tags: Venue default tags.
            :param droplet_ids: Optional droplet ids to attach.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the firewall.
        """
        existing = self.find(run_id=run_id, name=desired.name)
        neutral_tags = base_resource_tags(
            run_id=run_id, resource_name=desired.name,
            resource_kind=self.KIND, extra=dict(desired.tags),
            defaults=default_tags,
        )
        do_tags = to_do(neutral_tags=neutral_tags)
        effective_droplets = droplet_ids if droplet_ids is not None else []

        body: Dict[str, Any] = {
            "name": "codecraftai-fw-{}".format(desired.name),
            "inbound_rules": _inbound_rules(group=desired),
            "outbound_rules": _outbound_rules(group=desired),
            "tags": do_tags,
            "droplet_ids": list(effective_droplets),
        }

        if existing is None:
            created = self._client.firewalls.create(body=body)
            existing = created.get("firewall", {})
        elif not self.matches(existing=existing, desired=desired):
            firewall_id = existing.get("id", "")
            updated = self._client.firewalls.update(firewall_id=firewall_id,
                                                    body=body)
            existing = updated.get("firewall", existing)

        attributes: Dict[str, Any] = {}
        attributes["firewall_id"] = existing.get("id", "")

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name,
            venue_id=str(existing.get("id", "")),
            attributes=attributes, tags=neutral_tags,
        )
        return rtnval

    def destroy(self, *, run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned firewall for the run.

            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of destroyed firewall ids.
        """
        deleted: List[str] = []
        for firewall in self._all_firewalls():
            do_tags = firewall.get("tags", [])
            if not belongs_to_run(do_tags=do_tags, run_id=run_id):
                continue
            firewall_id = firewall.get("id", "")
            try:
                self._client.firewalls.delete(firewall_id=firewall_id)
                deleted.append(str(firewall_id))
            except Exception:
                pass
        rtnval = deleted
        return rtnval

    def list_owned(self, *, run_id: str) -> List[ProvisionedResource]:
        """
            Return all owned firewalls for the run as ProvisionedResources.

            :param run_id: Run identifier.

            :returns: List of ProvisionedResource entries.
        """
        out: List[ProvisionedResource] = []
        for firewall in self._all_firewalls():
            do_tags = firewall.get("tags", [])
            if not belongs_to_run(do_tags=do_tags, run_id=run_id):
                continue
            flat = to_flat(do_tags=do_tags)
            name = flat.get(RESOURCE_NAME_TAG_KEY, "")
            if len(name) == 0:
                continue
            attributes: Dict[str, Any] = {}
            attributes["firewall_id"] = firewall.get("id", "")
            entry = ProvisionedResource(
                kind=self.KIND, name=name,
                venue_id=str(firewall.get("id", "")),
                attributes=attributes, tags=from_do(do_tags=do_tags),
            )
            out.append(entry)
        rtnval = out
        return rtnval
