"""
    .. module:: clusternetworkmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: OCI RDMA Cluster Network manager — the Oracle Cloud HPC
               differentiator (RoCEv2, up to 3200 Gbps).

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

from ccai.provisioning.venues.oracle.ocisessionfactory import (
    OciSessionFactory
)
from ccai.provisioning.venues.oracle.ociidempotency import (
    belongs_to_run, matches_resource
)
from ccai.provisioning.venues.oracle.ocitagging import (
    base_resource_tags, to_freeform
)




class ClusterNetworkManager:
    """
        Manager for OCI RDMA Cluster Networks.

        Cluster Networks are OCI's HPC differentiator: a RoCEv2 RDMA fabric
        for GPU training pods (up to 3200 Gbps).  Instances that share an
        ``interconnect_group`` with ``CloudInterconnect(kind=OCI_RDMA)`` are
        all placed inside one Cluster Network.  Idempotent ``ensure`` is done
        by freeform-tag lookup against the ComputeManagementClient.
    """

    KIND: str = "cluster_network"

    def __init__(self, *, session_factory: OciSessionFactory) -> None:
        """
            Construct a ClusterNetworkManager.

            :param session_factory: OciSessionFactory.
        """
        self._session_factory: OciSessionFactory = session_factory
        return

    def _cm(self) -> Any:
        """
            Return the OCI ComputeManagementClient.

            :returns: An ``oci`` ComputeManagementClient.
        """
        rtnval = self._session_factory.client(
            service_name="compute_management"
        )
        return rtnval

    def find(self, *, run_id: str, group_name: str) -> Optional[Any]:
        """
            Find an existing owned Cluster Network by run+group freeform tags.

            :param run_id: Run identifier.
            :param group_name: Interconnect group label.

            :returns: The OCI ClusterNetwork summary, or None.
        """
        client = self._cm()
        compartment_id = self._session_factory.region_config.compartment_id
        cn_name = "{}-cn".format(group_name)
        response = list_call_get_all_results(
            client.list_cluster_networks,
            compartment_id=compartment_id
        )
        for cluster in response.data:
            if matches_resource(entity=cluster, run_id=run_id,
                                resource_name=cn_name):
                rtnval: Optional[Any] = cluster
                return rtnval
        rtnval = None
        return rtnval

    def ensure(self, *, run_id: str, group_name: str, shape: str,
               topology: str, availability_domain: str, subnet_id: str,
               image_id: str, member_count: int,
               default_tags: List[Dict[str, str]],
               aspects: Any) -> Dict[str, Any]:
        """
            Create or reuse an RDMA Cluster Network for an interconnect group.

            :param run_id: Run identifier.
            :param group_name: Interconnect group label.
            :param shape: Resolved BM.GPU shape for the cluster members.
            :param topology: Interconnect topology hint.
            :param availability_domain: Availability domain for the cluster.
            :param subnet_id: OCI subnet OCID for the instance pool.
            :param image_id: OCI image OCID for the instance pool.
            :param member_count: Number of instances to place in the cluster.
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: A dict ``{"cluster_network_id", "existed"}``.
        """

        client = self._cm()
        compartment_id = self._session_factory.region_config.compartment_id
        cn_name = "{}-cn".format(group_name)

        existing = self.find(run_id=run_id, group_name=group_name)
        if existing is not None:
            rtnval = {
                "cluster_network_id": getattr(existing, "id", ""),
                "existed": True,
            }
            return rtnval

        neutral_tags = base_resource_tags(
            run_id=run_id, resource_name=cn_name,
            resource_kind=self.KIND, defaults=default_tags,
        )
        freeform = to_freeform(neutral_tags=neutral_tags)

        # The cluster network's instance pool references a pre-built
        # InstanceConfiguration resource by OCID.  The shape, image and
        # placement are captured on that configuration; the cluster network
        # only carries the pool size and AD placement.
        placement = ocimodels.ClusterNetworkPlacementConfigurationDetails(
            availability_domain=availability_domain,
            primary_subnet_id=subnet_id,
        )
        instance_config_id = self._ensure_instance_configuration(
            run_id=run_id, group_name=group_name, shape=shape,
            image_id=image_id, subnet_id=subnet_id, freeform=freeform,
        )
        pool_details = ocimodels.CreateClusterNetworkInstancePoolDetails(
            instance_configuration_id=instance_config_id,
            size=member_count,
            display_name="codecraftai-{}-{}-pool".format(run_id, cn_name),
        )
        create_details = ocimodels.CreateClusterNetworkDetails(
            compartment_id=compartment_id,
            display_name="codecraftai-{}-{}".format(run_id, cn_name),
            instance_pools=[pool_details],
            placement_configuration=placement,
            freeform_tags=freeform,
        )
        created = client.create_cluster_network(
            create_cluster_network_details=create_details
        )

        rtnval = {
            "cluster_network_id": getattr(created.data, "id", ""),
            "existed": False,
        }
        return rtnval

    def _ensure_instance_configuration(self, *, run_id: str,
                                       group_name: str, shape: str,
                                       image_id: str, subnet_id: str,
                                       freeform: Dict[str, str]) -> str:
        """
            Create the InstanceConfiguration backing a cluster network pool.

            :param run_id: Run identifier.
            :param group_name: Interconnect group label.
            :param shape: Resolved BM.GPU shape.
            :param image_id: OCI image OCID.
            :param subnet_id: OCI subnet OCID.
            :param freeform: Freeform-tag dict carrying the owner triple.

            :returns: The InstanceConfiguration OCID.
        """

        client = self._cm()
        compartment_id = self._session_factory.region_config.compartment_id
        cfg_name = "{}-cn-config".format(group_name)

        vnic = ocimodels.InstanceConfigurationCreateVnicDetails(
            subnet_id=subnet_id
        )
        source = ocimodels.InstanceConfigurationInstanceSourceViaImageDetails(
            image_id=image_id
        )
        launch = ocimodels.InstanceConfigurationLaunchInstanceDetails(
            compartment_id=compartment_id,
            shape=shape,
            create_vnic_details=vnic,
            source_details=source,
            display_name="codecraftai-{}-{}".format(run_id, cfg_name),
        )
        instance_details = ocimodels.ComputeInstanceDetails(
            launch_details=launch
        )
        config_details = ocimodels.CreateInstanceConfigurationDetails(
            compartment_id=compartment_id,
            display_name="codecraftai-{}-{}".format(run_id, cfg_name),
            instance_details=instance_details,
            freeform_tags=dict(freeform),
        )
        created = client.create_instance_configuration(
            create_instance_configuration=config_details
        )
        rtnval = getattr(created.data, "id", "")
        return rtnval

    def destroy(self, *, run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned Cluster Network for the run.

            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of destroyed Cluster Network OCIDs.
        """
        client = self._cm()
        compartment_id = self._session_factory.region_config.compartment_id
        deleted: List[str] = []
        response = list_call_get_all_results(
            client.list_cluster_networks,
            compartment_id=compartment_id
        )
        for cluster in response.data:
            if not belongs_to_run(entity=cluster, run_id=run_id):
                continue
            cluster_id = getattr(cluster, "id", "")
            try:
                client.terminate_cluster_network(
                    cluster_network_id=cluster_id
                )
                deleted.append(cluster_id)
            except Exception:
                # Best-effort teardown sweep; a resource that fails to delete is left out
                # of the returned list and the sweep continues with the remaining resources.
                pass
        rtnval = deleted
        return rtnval
