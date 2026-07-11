"""
    .. module:: dnsmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: OCI DNS RRSet manager for the Oracle Cloud venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Any, Dict, List

from ccai.provisioning.model.cloud.clouddnsrecord import CloudDnsRecord
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.venues.oracle.ocisessionfactory import (
    OciSessionFactory
)
from ccai.provisioning.venues.oracle.ocierrors import OciValidationError



import oci

class DnsManager:
    """
        Manager for OCI DNS RRSets.

        The DNS zone is looked up by ``zone`` name; records are upserted via
        ``update_rr_set`` (the OCI replace-record-set verb).
    """

    KIND: str = "dns"

    def __init__(self, *, session_factory: OciSessionFactory) -> None:
        """
            Construct a DnsManager.

            :param session_factory: OciSessionFactory.
        """
        self._session_factory: OciSessionFactory = session_factory
        return

    def _dns(self) -> Any:
        """
            Return the OCI DnsClient.

            :returns: An ``oci`` DnsClient.
        """
        rtnval = self._session_factory.client(service_name="dns")
        return rtnval

    def _zone_name(self, *, zone: str) -> str:
        """
            Resolve the DNS zone, raising when it cannot be found.

            :param zone: DNS zone name (with or without trailing dot).

            :returns: The OCI zone name string.
            :raises: OciValidationError
        """
        target = zone[:-1] if zone.endswith(".") else zone
        client = self._dns()
        compartment_id = self._session_factory.region_config.compartment_id
        response = oci.pagination.list_call_get_all_results(client.list_zones, compartment_id=compartment_id)
        for entry in response.data:
            if getattr(entry, "name", "") == target:
                rtnval = target
                return rtnval

        err_msg_lines = ["OCI DNS zone not found for record."]
        err_msg_lines.append("ZONE: {}".format(zone))
        err_msg = os.linesep.join(err_msg_lines)
        raise OciValidationError(err_msg)

    def ensure(self, *, desired: CloudDnsRecord, run_id: str,
               aspects: Any) -> ProvisionedResource:
        """
            Upsert an OCI DNS RRSet.

            :param desired: Desired CloudDnsRecord.
            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the record.
        """
        import oci

        zone_name = self._zone_name(zone=desired.zone)
        client = self._dns()

        records: List[Any] = []
        for value in desired.values:
            records.append(oci.dns.models.RecordDetails(
                domain=desired.name,
                rtype=desired.record_type,
                ttl=desired.ttl_seconds,
                rdata=value,
            ))
        rrset_details = oci.dns.models.UpdateRRSetDetails(items=records)
        client.update_rr_set(
            zone_name_or_id=zone_name,
            domain=desired.name,
            rtype=desired.record_type,
            update_rr_set_details=rrset_details,
        )

        attributes: Dict[str, Any] = {}
        attributes["zone"] = zone_name
        attributes["record_type"] = desired.record_type
        attributes["values"] = list(desired.values)
        attributes["ttl_seconds"] = desired.ttl_seconds

        venue_id = "{}#{}#{}".format(zone_name, desired.name,
                                     desired.record_type)
        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=venue_id,
            attributes=attributes, tags={},
        )
        return rtnval

    def destroy_record(self, *, desired: CloudDnsRecord,
                       aspects: Any) -> None:
        """
            Delete an OCI DNS RRSet.

            :param desired: The CloudDnsRecord that was previously upserted.
            :param aspects: Aspects.
        """
        try:
            zone_name = self._zone_name(zone=desired.zone)
        except OciValidationError:
            return

        client = self._dns()
        try:
            client.delete_rr_set(
                zone_name_or_id=zone_name,
                domain=desired.name,
                rtype=desired.record_type,
            )
        except Exception:
            return
        return
