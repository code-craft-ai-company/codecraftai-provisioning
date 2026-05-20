"""
    .. module:: dnsmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Cloud DNS record manager for the Google venue.

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
from automojo.provisioning.venues.google.gcpsessionfactory import (
    GcpSessionFactory, SERVICE_DNS
)


class DnsManager:
    """
        Manager for Cloud DNS record sets.

        Records are upserted into a managed zone resolved by ``zone``.  v1
        has no read-side diff: ``ensure`` performs an upsert change every
        apply (idempotent at the API level).
    """

    KIND: str = "dns"

    def __init__(self, *, session_factory: GcpSessionFactory) -> None:
        """
            Construct a DnsManager.

            :param session_factory: GcpSessionFactory.
        """
        self._session_factory: GcpSessionFactory = session_factory
        return

    def _client(self) -> Any:
        """
            Return the Cloud DNS client.

            :returns: The DNS client.
        """
        rtnval = self._session_factory.client(service_name=SERVICE_DNS)
        return rtnval

    def ensure(self, *, desired: CloudDnsRecord, run_id: str,
               aspects: Any) -> ProvisionedResource:
        """
            Upsert a Cloud DNS record set.

            :param desired: Desired CloudDnsRecord.
            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the record set.
        """
        client = self._client()
        record_body: Dict[str, Any] = {
            "name": desired.name,
            "type": desired.record_type,
            "ttl": desired.ttl_seconds,
            "rrdatas": list(desired.values),
        }
        client.upsert_record_set(zone_name=desired.zone,
                                 record_set=record_body)

        attributes: Dict[str, Any] = {}
        attributes["zone"] = desired.zone
        attributes["record_type"] = desired.record_type
        attributes["values"] = list(desired.values)

        venue_id = "{}/{}/{}".format(desired.zone, desired.name,
                                     desired.record_type)
        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=venue_id,
            attributes=attributes,
        )
        return rtnval

    def destroy_record(self, *, desired: CloudDnsRecord,
                        aspects: Any) -> None:
        """
            Delete a Cloud DNS record set.

            :param desired: The CloudDnsRecord to remove.
            :param aspects: Aspects.
        """
        client = self._client()
        record_body: Dict[str, Any] = {
            "name": desired.name,
            "type": desired.record_type,
        }
        try:
            client.delete_record_set(zone_name=desired.zone,
                                     record_set=record_body)
        except Exception:
            pass
        return

    def list_owned(self, *, run_id: str) -> List[ProvisionedResource]:
        """
            Return owned DNS records (no read-side enumeration in v1).

            :param run_id: Run identifier.

            :returns: An empty list.
        """
        rtnval: List[ProvisionedResource] = []
        return rtnval
