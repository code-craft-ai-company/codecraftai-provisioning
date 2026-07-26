"""
    .. module:: subnetmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: OCI Subnet manager for the Oracle Cloud venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []

from ccai.restclient.oracle import ocimodels

from ccai.restclient.oracle.ocipagination import (
    list_call_get_all_results
)


from typing import Any, Dict, List, Optional

from ccai.provisioning.model.cloud.cloudsubnet import CloudSubnet
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




class SubnetManager:
    """
        Manager for OCI Subnets.

        Subnets are bound to a parent VCN.  Public subnets receive the VCN's
        public route table and a non-empty list of security lists.  The
        ``zone`` field maps to an OCI availability domain; an empty zone
        produces a regional subnet.
    """

    KIND: str = "subnet"

    def __init__(self, *, session_factory: OciSessionFactory) -> None:
        """
            Construct a SubnetManager.

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
            Find an existing owned subnet by run+name freeform tags.

            :param run_id: Run identifier.
            :param name: Neutral subnet name.

            :returns: The OCI Subnet model object or None.
        """
        client = self._vn()
        compartment_id = self._session_factory.region_config.compartment_id
        response = list_call_get_all_results(client.list_subnets, compartment_id=compartment_id)
        for subnet in response.data:
            if matches_resource(entity=subnet, run_id=run_id,
                                resource_name=name):
                rtnval: Optional[Any] = subnet
                return rtnval
        rtnval = None
        return rtnval

    def ensure(self, *, desired: CloudSubnet, run_id: str, vcn_id: str,
               route_table_id: Optional[str],
               security_list_ids: Optional[List[str]],
               default_tags: List[Dict[str, str]],
               aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for a subnet.

            :param desired: Desired CloudSubnet.
            :param run_id: Run identifier.
            :param vcn_id: OCI VCN OCID of the parent network.
            :param route_table_id: Optional route table OCID (public subnet).
            :param security_list_ids: Optional security list OCIDs.
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the subnet.
        """

        client = self._vn()
        compartment_id = self._session_factory.region_config.compartment_id
        existing = self.find(run_id=run_id, name=desired.name)

        if existing is None:
            neutral_tags = base_resource_tags(
                run_id=run_id, resource_name=desired.name,
                resource_kind=self.KIND, extra=dict(desired.tags),
                defaults=default_tags,
            )
            details_kwargs: Dict[str, Any] = {}
            details_kwargs["compartment_id"] = compartment_id
            details_kwargs["vcn_id"] = vcn_id
            details_kwargs["cidr_block"] = desired.cidr
            details_kwargs["display_name"] = "codecraftai-{}-{}".format(
                run_id, desired.name
            )
            details_kwargs["freeform_tags"] = to_freeform(
                neutral_tags=neutral_tags
            )
            if desired.zone is not None and len(desired.zone) > 0:
                details_kwargs["availability_domain"] = desired.zone
            if route_table_id is not None and len(route_table_id) > 0:
                details_kwargs["route_table_id"] = route_table_id
            if security_list_ids is not None and len(security_list_ids) > 0:
                details_kwargs["security_list_ids"] = list(security_list_ids)
            if desired.public is not True:
                details_kwargs["prohibit_public_ip_on_vnic"] = True

            details = ocimodels.CreateSubnetDetails(**details_kwargs)
            created = client.create_subnet(create_subnet_details=details)
            existing = created.data

        subnet_id = getattr(existing, "id", "")

        attributes: Dict[str, Any] = {}
        attributes["subnet_id"] = subnet_id
        attributes["vcn_id"] = vcn_id
        attributes["cidr"] = getattr(existing, "cidr_block", desired.cidr)
        attributes["zone"] = getattr(existing, "availability_domain",
                                     desired.zone)
        attributes["public"] = desired.public

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=subnet_id,
            attributes=attributes,
            tags=from_freeform(
                freeform_tags=getattr(existing, "freeform_tags", None)
            ),
        )
        return rtnval

    def destroy(self, *, run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned subnet for the run.

            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of destroyed subnet OCIDs.
        """
        client = self._vn()
        compartment_id = self._session_factory.region_config.compartment_id
        deleted: List[str] = []
        response = list_call_get_all_results(client.list_subnets, compartment_id=compartment_id)
        for subnet in response.data:
            if not belongs_to_run(entity=subnet, run_id=run_id):
                continue
            subnet_id = getattr(subnet, "id", "")
            try:
                client.delete_subnet(subnet_id=subnet_id)
                deleted.append(subnet_id)
            except Exception:
                pass
        rtnval = deleted
        return rtnval

    def list_owned(self, *, run_id: str) -> List[ProvisionedResource]:
        """
            Return all owned subnets for the run as ProvisionedResources.

            :param run_id: Run identifier.

            :returns: List of ProvisionedResource entries.
        """
        client = self._vn()
        compartment_id = self._session_factory.region_config.compartment_id
        out: List[ProvisionedResource] = []
        response = list_call_get_all_results(client.list_subnets, compartment_id=compartment_id)
        for subnet in response.data:
            if not belongs_to_run(entity=subnet, run_id=run_id):
                continue
            name = resource_name_of(entity=subnet)
            if name is None:
                continue
            attributes: Dict[str, Any] = {}
            attributes["subnet_id"] = getattr(subnet, "id", "")
            attributes["vcn_id"] = getattr(subnet, "vcn_id", "")
            attributes["cidr"] = getattr(subnet, "cidr_block", "")
            entry = ProvisionedResource(
                kind=self.KIND, name=name,
                venue_id=getattr(subnet, "id", ""),
                attributes=attributes,
                tags=from_freeform(
                    freeform_tags=getattr(subnet, "freeform_tags", None)
                ),
            )
            out.append(entry)
        rtnval = out
        return rtnval
