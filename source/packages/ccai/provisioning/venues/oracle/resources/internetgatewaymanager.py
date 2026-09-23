"""
    .. module:: internetgatewaymanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: OCI Internet Gateway manager for the Oracle Cloud venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []

from ccai.restclient.oracle import ocimodels

from ccai.restclient.oracle.ocipagination import (
    list_call_get_all_results
)


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




class InternetGatewayManager:
    """
        Manager for OCI Internet Gateways.

        An Internet Gateway is created per VCN to give public subnets
        outbound/inbound connectivity.  Idempotent ``ensure`` is done by
        freeform-tag lookup scoped to the parent VCN.
    """

    KIND: str = "internet_gateway"

    def __init__(self, *, session_factory: OciSessionFactory) -> None:
        """
            Construct an InternetGatewayManager.

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

    def ensure(self, *, run_id: str, network_name: str, vcn_id: str,
               default_tags: List[Dict[str, str]], aspects: Any) -> str:
        """
            Create or reuse an Internet Gateway attached to the VCN.

            :param run_id: Run identifier.
            :param network_name: Neutral network name.
            :param vcn_id: OCI VCN OCID to attach to.
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: The Internet Gateway OCID.
        """

        client = self._vn()
        compartment_id = self._session_factory.region_config.compartment_id
        igw_name = "{}-igw".format(network_name)

        response = list_call_get_all_results(
            client.list_internet_gateways,
            compartment_id=compartment_id, vcn_id=vcn_id
        )
        for gateway in response.data:
            if matches_resource(entity=gateway, run_id=run_id,
                                resource_name=igw_name):
                rtnval = getattr(gateway, "id", "")
                return rtnval

        neutral_tags = base_resource_tags(
            run_id=run_id, resource_name=igw_name,
            resource_kind=self.KIND, defaults=default_tags,
        )
        details = ocimodels.CreateInternetGatewayDetails(
            compartment_id=compartment_id,
            vcn_id=vcn_id,
            is_enabled=True,
            display_name="codecraftai-{}-{}".format(run_id, igw_name),
            freeform_tags=to_freeform(neutral_tags=neutral_tags),
        )
        created = client.create_internet_gateway(
            create_internet_gateway_details=details
        )
        rtnval = getattr(created.data, "id", "")
        return rtnval

    def destroy(self, *, run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned Internet Gateway for the run.

            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of destroyed Internet Gateway OCIDs.
        """
        client = self._vn()
        compartment_id = self._session_factory.region_config.compartment_id
        deleted: List[str] = []
        response = list_call_get_all_results(
            client.list_internet_gateways,
            compartment_id=compartment_id
        )
        for gateway in response.data:
            if not belongs_to_run(entity=gateway, run_id=run_id):
                continue
            igw_id = getattr(gateway, "id", "")
            try:
                client.delete_internet_gateway(ig_id=igw_id)
                deleted.append(igw_id)
            except Exception:
                # Best-effort teardown sweep; a resource that fails to delete is left out
                # of the returned list and the sweep continues with the remaining resources.
                pass
        rtnval = deleted
        return rtnval
