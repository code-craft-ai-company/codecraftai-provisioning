"""
    .. module:: dnsmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Cloud DNS record manager for the Google venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List

from ccai.provisioning.model.cloud.clouddnsrecord import CloudDnsRecord
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.venues.google.gcpsessionfactory import (
    GcpSessionFactory, SERVICE_DNS
)


class DnsManager:
    """
        Manager for Cloud DNS record sets.

        Records are upserted into a pre-existing managed zone resolved by
        ``zone``.  v1 is attach-only: the managed zone must already exist.
        ``ensure`` deletes any current record set with the same name+type and
        re-creates it in a single change, which is idempotent at the API
        level.
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
        zone = client.zone(desired.zone)

        new_record = zone.resource_record_set(
            desired.name, desired.record_type, desired.ttl_seconds,
            list(desired.values),
        )

        changes = zone.changes()
        for record in zone.list_resource_record_sets():
            if (record.name == desired.name
                    and record.record_type == desired.record_type):
                changes.delete_record_set(record)
        changes.add_record_set(new_record)
        changes.create()

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
        try:
            zone = client.zone(desired.zone)
            changes = zone.changes()
            pending = 0
            for record in zone.list_resource_record_sets():
                if (record.name == desired.name
                        and record.record_type == desired.record_type):
                    changes.delete_record_set(record)
                    pending += 1
            if pending > 0:
                changes.create()
        except Exception:
            # Best-effort teardown of the DNS record; a record that cannot be deleted
            # must not stop the remaining resources of the run from being torn down.
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
