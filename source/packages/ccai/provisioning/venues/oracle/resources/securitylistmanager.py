"""
    .. module:: securitylistmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: OCI Security List manager for the Oracle Cloud venue.

    OCI Security Lists are list-based (a single ordered list of ingress and
    egress rules attached to a subnet), not group-based like AWS Security
    Groups.  Each neutral CloudSecurityGroup maps to one OCI Security List.

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
from ccai.provisioning.venues.oracle.ocisessionfactory import (
    OciSessionFactory
)
from ccai.provisioning.venues.oracle.ociidempotency import (
    belongs_to_run, matches_resource, resource_name_of
)
from ccai.provisioning.venues.oracle.ocitagging import (
    base_resource_tags, from_freeform, to_freeform
)


# Neutral protocol → OCI security-list protocol number ("all" is "all").
_PROTOCOL_NUMBERS: Dict[str, str] = {
    "tcp": "6",
    "udp": "17",
    "icmp": "1",
    "all": "all",
}


def _protocol_number(*, protocol: str) -> str:
    """
        Map a neutral protocol token to an OCI protocol number string.

        :param protocol: Neutral protocol token.

        :returns: OCI protocol number string (or "all").
    """
    rtnval = _PROTOCOL_NUMBERS.get(protocol, "all")
    return rtnval



import oci

class SecurityListManager:
    """
        Manager for OCI Security Lists.

        OCI realises subnet-level firewalling through Security Lists — an
        ordered list of stateful ingress/egress rules.  Each neutral
        :class:`CloudSecurityGroup` becomes one Security List.  Idempotent
        ``ensure`` is done by freeform-tag lookup.
    """

    KIND: str = "security_group"

    def __init__(self, *, session_factory: OciSessionFactory) -> None:
        """
            Construct a SecurityListManager.

            :param session_factory: OciSessionFactory.
        """
        self._session_factory: OciSessionFactory = session_factory
        return

    def _vn(self) -> Any:
        """
            Return the OCI VirtualNetworkClient.

            :returns: An ``oci`` VirtualNetworkClient.
        """
        rtnval = self._session_factory.client(service_name="virtual_network")
        return rtnval

    def find(self, *, run_id: str, name: str) -> Optional[Any]:
        """
            Find an existing owned Security List by run+name freeform tags.

            :param run_id: Run identifier.
            :param name: Neutral security group name.

            :returns: The OCI SecurityList model object or None.
        """
        client = self._vn()
        compartment_id = self._session_factory.region_config.compartment_id
        response = oci.pagination.list_call_get_all_results(client.list_security_lists, compartment_id=compartment_id)
        for seclist in response.data:
            if matches_resource(entity=seclist, run_id=run_id,
                                resource_name=name):
                rtnval: Optional[Any] = seclist
                return rtnval
        rtnval = None
        return rtnval

    def _build_ingress_rules(self, *, desired: CloudSecurityGroup
                             ) -> List[Any]:
        """
            Translate neutral ingress rules to OCI IngressSecurityRule list.

            :param desired: Desired CloudSecurityGroup.

            :returns: A list of ``oci`` IngressSecurityRule objects.
        """
        import oci

        out: List[Any] = []
        rules = desired.ingress_rules if desired.ingress_rules is not None else []
        for rule in rules:
            cidrs = list(rule.source_cidrs) if rule.source_cidrs is not None else ["0.0.0.0/0"]
            protocol = _protocol_number(protocol=rule.protocol)
            for cidr in cidrs:
                rule_kwargs: Dict[str, Any] = {}
                rule_kwargs["protocol"] = protocol
                rule_kwargs["source"] = cidr
                rule_kwargs["source_type"] = "CIDR_BLOCK"
                rule_kwargs["is_stateless"] = False
                if protocol == "6" or protocol == "17":
                    port_range = oci.core.models.PortRange(
                        min=rule.from_port, max=rule.to_port
                    )
                    if protocol == "6":
                        rule_kwargs["tcp_options"] = (
                            oci.core.models.TcpOptions(
                                destination_port_range=port_range
                            )
                        )
                    else:
                        rule_kwargs["udp_options"] = (
                            oci.core.models.UdpOptions(
                                destination_port_range=port_range
                            )
                        )
                out.append(oci.core.models.IngressSecurityRule(**rule_kwargs))
        rtnval = out
        return rtnval

    def _build_egress_rules(self, *, desired: CloudSecurityGroup
                            ) -> List[Any]:
        """
            Translate neutral egress rules to OCI EgressSecurityRule list.

            :param desired: Desired CloudSecurityGroup.

            :returns: A list of ``oci`` EgressSecurityRule objects.
        """
        import oci

        out: List[Any] = []
        rules = desired.egress_rules if desired.egress_rules is not None else []
        for rule in rules:
            cidrs = list(rule.dest_cidrs) if rule.dest_cidrs is not None else ["0.0.0.0/0"]
            protocol = _protocol_number(protocol=rule.protocol)
            for cidr in cidrs:
                rule_kwargs: Dict[str, Any] = {}
                rule_kwargs["protocol"] = protocol
                rule_kwargs["destination"] = cidr
                rule_kwargs["destination_type"] = "CIDR_BLOCK"
                rule_kwargs["is_stateless"] = False
                if protocol == "6" or protocol == "17":
                    port_range = oci.core.models.PortRange(
                        min=rule.from_port, max=rule.to_port
                    )
                    if protocol == "6":
                        rule_kwargs["tcp_options"] = (
                            oci.core.models.TcpOptions(
                                destination_port_range=port_range
                            )
                        )
                    else:
                        rule_kwargs["udp_options"] = (
                            oci.core.models.UdpOptions(
                                destination_port_range=port_range
                            )
                        )
                out.append(oci.core.models.EgressSecurityRule(**rule_kwargs))

        if len(out) == 0:
            # OCI requires at least one egress rule; default allow-all.
            out.append(oci.core.models.EgressSecurityRule(
                protocol="all", destination="0.0.0.0/0",
                destination_type="CIDR_BLOCK", is_stateless=False,
            ))
        rtnval = out
        return rtnval

    def ensure(self, *, desired: CloudSecurityGroup, run_id: str,
               vcn_id: str, default_tags: List[Dict[str, str]],
               aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for a Security List.

            :param desired: Desired CloudSecurityGroup.
            :param run_id: Run identifier.
            :param vcn_id: Parent VCN OCID.
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the Security List.
        """
        import oci

        client = self._vn()
        compartment_id = self._session_factory.region_config.compartment_id
        existing = self.find(run_id=run_id, name=desired.name)

        ingress_rules = self._build_ingress_rules(desired=desired)
        egress_rules = self._build_egress_rules(desired=desired)

        if existing is None:
            neutral_tags = base_resource_tags(
                run_id=run_id, resource_name=desired.name,
                resource_kind=self.KIND, extra=dict(desired.tags),
                defaults=default_tags,
            )
            details = oci.core.models.CreateSecurityListDetails(
                compartment_id=compartment_id,
                vcn_id=vcn_id,
                ingress_security_rules=ingress_rules,
                egress_security_rules=egress_rules,
                display_name="codecraftai-{}-{}".format(run_id, desired.name),
                freeform_tags=to_freeform(neutral_tags=neutral_tags),
            )
            created = client.create_security_list(
                create_security_list_details=details
            )
            existing = created.data

        seclist_id = getattr(existing, "id", "")

        attributes: Dict[str, Any] = {}
        attributes["security_list_id"] = seclist_id
        attributes["vcn_id"] = vcn_id
        attributes["ingress_count"] = len(ingress_rules)
        attributes["egress_count"] = len(egress_rules)

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=seclist_id,
            attributes=attributes,
            tags=from_freeform(
                freeform_tags=getattr(existing, "freeform_tags", None)
            ),
        )
        return rtnval

    def rules_drifted(self, *, existing: Any,
                      desired: CloudSecurityGroup) -> bool:
        """
            Detect whether the security-list rule count has drifted.

            :param existing: OCI SecurityList model object.
            :param desired: Desired CloudSecurityGroup.

            :returns: True when the desired rule shape differs.
        """
        desired_ingress = self._build_ingress_rules(desired=desired)
        existing_ingress = getattr(existing, "ingress_security_rules", None)
        existing_count = len(existing_ingress) if existing_ingress is not None else 0
        rtnval = existing_count != len(desired_ingress)
        return rtnval

    def destroy(self, *, run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned Security List for the run.

            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of destroyed Security List OCIDs.
        """
        client = self._vn()
        compartment_id = self._session_factory.region_config.compartment_id
        deleted: List[str] = []
        response = oci.pagination.list_call_get_all_results(client.list_security_lists, compartment_id=compartment_id)
        for seclist in response.data:
            if not belongs_to_run(entity=seclist, run_id=run_id):
                continue
            seclist_id = getattr(seclist, "id", "")
            try:
                client.delete_security_list(security_list_id=seclist_id)
                deleted.append(seclist_id)
            except Exception:
                pass
        rtnval = deleted
        return rtnval

    def list_owned(self, *, run_id: str) -> List[ProvisionedResource]:
        """
            Return all owned Security Lists for the run.

            :param run_id: Run identifier.

            :returns: List of ProvisionedResource entries.
        """
        client = self._vn()
        compartment_id = self._session_factory.region_config.compartment_id
        out: List[ProvisionedResource] = []
        response = oci.pagination.list_call_get_all_results(client.list_security_lists, compartment_id=compartment_id)
        for seclist in response.data:
            if not belongs_to_run(entity=seclist, run_id=run_id):
                continue
            name = resource_name_of(entity=seclist)
            if name is None:
                continue
            attributes: Dict[str, Any] = {}
            attributes["security_list_id"] = getattr(seclist, "id", "")
            attributes["vcn_id"] = getattr(seclist, "vcn_id", "")
            entry = ProvisionedResource(
                kind=self.KIND, name=name,
                venue_id=getattr(seclist, "id", ""),
                attributes=attributes,
                tags=from_freeform(
                    freeform_tags=getattr(seclist, "freeform_tags", None)
                ),
            )
            out.append(entry)
        rtnval = out
        return rtnval
