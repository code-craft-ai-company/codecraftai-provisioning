"""
    .. module:: dnsmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Azure DNS record-set manager for the Azure venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List

from automojo.provisioning.model.cloud.clouddnsrecord import CloudDnsRecord
from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.venues.azure.azuresessionfactory import (
    AzureSessionFactory
)


def _record_set_payload(*, desired: CloudDnsRecord) -> Dict[str, Any]:
    """
        Build the Azure DNS record-set payload for a CloudDnsRecord.

        :param desired: The CloudDnsRecord.

        :returns: A dict in the Azure RecordSet schema.
    """
    out: Dict[str, Any] = {"ttl": desired.ttl_seconds}
    record_type = desired.record_type

    if record_type == "A":
        out["a_records"] = [{"ipv4_address": v} for v in desired.values]
    elif record_type == "AAAA":
        out["aaaa_records"] = [{"ipv6_address": v} for v in desired.values]
    elif record_type == "CNAME":
        out["cname_record"] = {"cname": desired.values[0]}
    elif record_type == "TXT":
        out["txt_records"] = [{"value": [v]} for v in desired.values]
    elif record_type == "MX":
        mx_records: List[Dict[str, Any]] = []
        for value in desired.values:
            parts = value.split(" ", 1)
            if len(parts) == 2:
                preference, exchange = parts
                mx_records.append({"preference": int(preference),
                                   "exchange": exchange})
            else:
                mx_records.append({"preference": 10, "exchange": value})
        out["mx_records"] = mx_records
    else:
        out["txt_records"] = [{"value": [v]} for v in desired.values]

    rtnval = out
    return rtnval


class DnsManager:
    """
        Manager for Azure DNS record sets.

        The DNS zone is resolved by ``zone`` name and must already exist;
        record sets are upserted via ``record_sets.create_or_update``.
    """

    KIND: str = "dns"

    def __init__(self, *, session_factory: AzureSessionFactory) -> None:
        """
            Construct a DnsManager.

            :param session_factory: AzureSessionFactory.
        """
        self._session_factory: AzureSessionFactory = session_factory
        return

    def _dns(self) -> Any:
        """
            Return the DnsManagementClient.

            :returns: A DnsManagementClient.
        """
        rtnval = self._session_factory.dns_client()
        return rtnval

    def ensure(self, *, desired: CloudDnsRecord, resource_group: str,
               run_id: str, aspects: Any) -> ProvisionedResource:
        """
            Upsert an Azure DNS record set.

            :param desired: Desired CloudDnsRecord.
            :param resource_group: ResourceGroup hosting the DNS zone.
            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the record set.
        """
        client = self._dns()
        payload = _record_set_payload(desired=desired)

        client.record_sets.create_or_update(
            resource_group_name=resource_group,
            zone_name=desired.zone,
            relative_record_set_name=desired.name,
            record_type=desired.record_type,
            parameters=payload,
        )

        attributes: Dict[str, Any] = {}
        attributes["zone"] = desired.zone
        attributes["record_type"] = desired.record_type
        attributes["values"] = list(desired.values)
        attributes["ttl_seconds"] = desired.ttl_seconds

        venue_id = "{}#{}#{}".format(desired.zone, desired.name,
                                     desired.record_type)
        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=venue_id,
            attributes=attributes, tags={},
        )
        return rtnval

    def destroy_record(self, *, desired: CloudDnsRecord,
                        resource_group: str, aspects: Any) -> None:
        """
            Delete an Azure DNS record set.

            :param desired: The CloudDnsRecord previously upserted.
            :param resource_group: ResourceGroup hosting the DNS zone.
            :param aspects: Aspects.
        """
        client = self._dns()
        try:
            client.record_sets.delete(
                resource_group_name=resource_group,
                zone_name=desired.zone,
                relative_record_set_name=desired.name,
                record_type=desired.record_type,
            )
        except Exception:
            return
        return
