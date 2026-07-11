"""
    .. module:: routetablemanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: OCI Route Table manager for the Oracle Cloud venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List

from ccai.provisioning.venues.oracle.ocisessionfactory import (
    OciSessionFactory
)
from ccai.provisioning.venues.oracle.ociidempotency import (
    belongs_to_run, matches_resource
)
from ccai.provisioning.venues.oracle.ocitagging import (
    base_resource_tags, to_freeform
)



import oci

class RouteTableManager:
    """
        Manager for OCI Route Tables.

        A public route table routes ``0.0.0.0/0`` through the VCN's
        Internet Gateway.  Idempotent ``ensure`` is done by freeform-tag
        lookup scoped to the parent VCN.
    """

    KIND: str = "route_table"

    def __init__(self, *, session_factory: OciSessionFactory) -> None:
        """
            Construct a RouteTableManager.

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

    def ensure_public(self, *, run_id: str, network_name: str, vcn_id: str,
                      igw_id: str, default_tags: List[Dict[str, str]],
                      aspects: Any) -> str:
        """
            Create or reuse a public route table for the VCN.

            :param run_id: Run identifier.
            :param network_name: Neutral network name.
            :param vcn_id: OCI VCN OCID.
            :param igw_id: OCI Internet Gateway OCID.
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: The route table OCID.
        """
        import oci

        client = self._vn()
        compartment_id = self._session_factory.region_config.compartment_id
        rt_name = "{}-public-rt".format(network_name)

        response = oci.pagination.list_call_get_all_results(
            client.list_route_tables,
            compartment_id=compartment_id, vcn_id=vcn_id
        )
        for table in response.data:
            if matches_resource(entity=table, run_id=run_id,
                                resource_name=rt_name):
                rtnval = getattr(table, "id", "")
                return rtnval

        neutral_tags = base_resource_tags(
            run_id=run_id, resource_name=rt_name,
            resource_kind=self.KIND, defaults=default_tags,
        )
        route_rule = oci.core.models.RouteRule(
            destination="0.0.0.0/0",
            destination_type="CIDR_BLOCK",
            network_entity_id=igw_id,
        )
        details = oci.core.models.CreateRouteTableDetails(
            compartment_id=compartment_id,
            vcn_id=vcn_id,
            route_rules=[route_rule],
            display_name="codecraftai-{}-{}".format(run_id, rt_name),
            freeform_tags=to_freeform(neutral_tags=neutral_tags),
        )
        created = client.create_route_table(
            create_route_table_details=details
        )
        rtnval = getattr(created.data, "id", "")
        return rtnval

    def destroy(self, *, run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned route table for the run.

            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of destroyed route table OCIDs.
        """
        client = self._vn()
        compartment_id = self._session_factory.region_config.compartment_id
        deleted: List[str] = []
        response = oci.pagination.list_call_get_all_results(client.list_route_tables, compartment_id=compartment_id)
        for table in response.data:
            if not belongs_to_run(entity=table, run_id=run_id):
                continue
            rt_id = getattr(table, "id", "")
            try:
                client.delete_route_table(rt_id=rt_id)
                deleted.append(rt_id)
            except Exception:
                pass
        rtnval = deleted
        return rtnval
