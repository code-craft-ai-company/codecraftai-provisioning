"""
    .. module:: vcnmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: OCI VCN (Virtual Cloud Network) manager — the OCI VPC equivalent.

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

from ccai.provisioning.model.cloud.cloudnetwork import CloudNetwork
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




class VcnManager:
    """
        Manager for OCI VCNs (Virtual Cloud Networks).

        VCNs are the OCI equivalent of an AWS VPC.  Each VCN is tagged with
        the venue owner/run/name freeform-tag triple.  Idempotent ``ensure``
        is done by freeform-tag lookup; an existing tagged VCN is reused.
    """

    KIND: str = "network"

    def __init__(self, *, session_factory: OciSessionFactory) -> None:
        """
            Construct a VcnManager.

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
            Find an existing owned VCN by run+name freeform tags.

            :param run_id: Run identifier.
            :param name: Neutral network name.

            :returns: The OCI Vcn model object, or None.
        """
        client = self._vn()
        compartment_id = self._session_factory.region_config.compartment_id
        response = list_call_get_all_results(client.list_vcns, compartment_id=compartment_id)
        for vcn in response.data:
            if matches_resource(entity=vcn, run_id=run_id,
                                resource_name=name):
                rtnval: Optional[Any] = vcn
                return rtnval
        rtnval = None
        return rtnval

    def matches(self, *, existing: Any, desired: CloudNetwork) -> bool:
        """
            Compare an existing VCN to the desired CloudNetwork.

            :param existing: OCI Vcn model object.
            :param desired: Desired CloudNetwork.

            :returns: True when the CIDR matches.
        """
        cidr_match = getattr(existing, "cidr_block", None) == desired.cidr
        rtnval = cidr_match
        return rtnval

    def ensure(self, *, desired: CloudNetwork, run_id: str,
               default_tags: List[Dict[str, str]],
               aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for a VCN.

            :param desired: Desired CloudNetwork.
            :param run_id: Run identifier (used for owner tagging).
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the VCN.
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
            details = ocimodels.CreateVcnDetails(
                compartment_id=compartment_id,
                cidr_block=desired.cidr,
                display_name="codecraftai-{}-{}".format(run_id, desired.name),
                freeform_tags=to_freeform(neutral_tags=neutral_tags),
            )
            created = client.create_vcn(create_vcn_details=details)
            existing = created.data

        vcn_id = getattr(existing, "id", "")

        attributes: Dict[str, Any] = {}
        attributes["vcn_id"] = vcn_id
        attributes["cidr"] = getattr(existing, "cidr_block", desired.cidr)
        attributes["region"] = desired.region

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=vcn_id,
            attributes=attributes,
            tags=from_freeform(
                freeform_tags=getattr(existing, "freeform_tags", None)
            ),
        )
        return rtnval

    def destroy(self, *, run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned VCN for the run.

            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of destroyed VCN OCIDs.
        """
        client = self._vn()
        compartment_id = self._session_factory.region_config.compartment_id
        deleted: List[str] = []
        response = list_call_get_all_results(client.list_vcns, compartment_id=compartment_id)
        for vcn in response.data:
            if not belongs_to_run(entity=vcn, run_id=run_id):
                continue
            vcn_id = getattr(vcn, "id", "")
            try:
                client.delete_vcn(vcn_id=vcn_id)
                deleted.append(vcn_id)
            except Exception:
                # Best-effort teardown sweep; a resource that fails to delete is left out
                # of the returned list and the sweep continues with the remaining resources.
                pass
        rtnval = deleted
        return rtnval

    def list_owned(self, *, run_id: str) -> List[ProvisionedResource]:
        """
            Return all owned VCNs for the run as ProvisionedResources.

            :param run_id: Run identifier.

            :returns: List of ProvisionedResource entries.
        """
        client = self._vn()
        compartment_id = self._session_factory.region_config.compartment_id
        out: List[ProvisionedResource] = []
        response = list_call_get_all_results(client.list_vcns, compartment_id=compartment_id)
        for vcn in response.data:
            if not belongs_to_run(entity=vcn, run_id=run_id):
                continue
            name = resource_name_of(entity=vcn)
            if name is None:
                continue
            attributes: Dict[str, Any] = {}
            attributes["vcn_id"] = getattr(vcn, "id", "")
            attributes["cidr"] = getattr(vcn, "cidr_block", "")
            entry = ProvisionedResource(
                kind=self.KIND, name=name,
                venue_id=getattr(vcn, "id", ""),
                attributes=attributes,
                tags=from_freeform(
                    freeform_tags=getattr(vcn, "freeform_tags", None)
                ),
            )
            out.append(entry)
        rtnval = out
        return rtnval
