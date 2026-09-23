"""
    .. module:: computemanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: OCI Compute Instance manager — user-data, GPU shapes,
               RDMA cluster placement, preemptible instances.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []

from ccai.restclient.oracle import ocimodels

from ccai.restclient.oracle.ocipagination import (
    list_call_get_all_results
)


import base64
import os

from typing import Any, Dict, List, Optional, Tuple

from ccai.provisioning.cloudinit.bootstraprenderer import (
    render_instance_user_data
)
from ccai.provisioning.model.cloud.cloudacceleratorcatalog import (
    CloudAcceleratorCatalog
)
from ccai.provisioning.model.cloud.cloudinstancesizecatalog import (
    CloudInstanceSizeCatalog
)
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance
from ccai.provisioning.model.cloud.preemptionpolicy import PreemptionPolicy
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.venues.oracle.ocisessionfactory import (
    OciSessionFactory
)
from ccai.provisioning.venues.oracle.ocierrors import OciValidationError
from ccai.provisioning.venues.oracle.ociidempotency import (
    belongs_to_run, matches_resource, resource_name_of
)
from ccai.provisioning.venues.oracle.ocitagging import (
    base_resource_tags, from_freeform, to_freeform
)
from ccai.provisioning.venues.oracle.resources.imageresolver import (
    ImageResolver
)


# OCI instance lifecycle states that count as "present".
_LIVE_STATES = frozenset({
    "PROVISIONING", "RUNNING", "STARTING", "STOPPING", "STOPPED",
})


def is_bm_gpu_shape(*, shape: str) -> bool:
    """
        Return True when an OCI shape is a bare-metal GPU shape.

        :param shape: OCI shape string.

        :returns: True for ``BM.GPU.*`` shapes.
    """
    rtnval = shape.startswith("BM.GPU")
    return rtnval




class ComputeManager:
    """
        Manager for OCI Compute Instances.

        Wires together:

        - cloud-init render via :func:`render_instance_user_data`,
        - GPU shape resolution via :class:`CloudAcceleratorCatalog`,
        - RDMA cluster-network membership when interconnect=OCI_RDMA,
        - preemption-policy → preemptible-instance config,
        - SSH key injection via ``metadata["ssh_authorized_keys"]``,
        - freeform-tag-based read-before-create for idempotence.
    """

    KIND: str = "instance"
    VENUE_NAME: str = "oracle"

    def __init__(self, *, session_factory: OciSessionFactory,
                 image_resolver: ImageResolver,
                 catalog: CloudAcceleratorCatalog) -> None:
        """
            Construct a ComputeManager.

            :param session_factory: OciSessionFactory.
            :param image_resolver: ImageResolver.
            :param catalog: CloudAcceleratorCatalog (for GPU shape lookup).
        """
        self._session_factory: OciSessionFactory = session_factory
        self._image_resolver: ImageResolver = image_resolver
        self._catalog: CloudAcceleratorCatalog = catalog
        return

    def _compute(self) -> Any:
        """
            Return the OCI ComputeClient.

            :returns: An ``oci`` ComputeClient.
        """
        rtnval = self._session_factory.client(service_name="compute")
        return rtnval

    def resolve_shape(self, *, instance: CloudInstance) -> str:
        """
            Resolve the OCI shape to launch.

            When ``accelerators`` is set, consult the accelerator catalog
            with the first accelerator's neutral model name (venue
            ``oracle``).  If the user also provided ``size``, the two must
            agree.  Otherwise return ``instance.size`` verbatim.

            :param instance: The neutral CloudInstance.

            :returns: OCI shape string.
            :raises: OciValidationError
        """
        accelerators = instance.accelerators if instance.accelerators is not None else []
        if len(accelerators) == 0:
            size_catalog = CloudInstanceSizeCatalog.default()
            native = size_catalog.resolve(token=instance.size,
                                          venue=self.VENUE_NAME)
            effective = native if native is not None else instance.size
            rtnval = effective
            return rtnval

        first = accelerators[0]
        try:
            sku = self._catalog.resolve(neutral_name=first.model,
                                        venue=self.VENUE_NAME)
        except Exception as xcpt:
            err_msg_lines = [
                "OCI instance accelerator could not be resolved by the "
                "catalog."
            ]
            err_msg_lines.append("INSTANCE: {}".format(instance.name))
            err_msg_lines.append("MODEL: {}".format(first.model))
            err_msg_lines.append("CAUSE: {}".format(xcpt))
            err_msg = os.linesep.join(err_msg_lines)
            raise OciValidationError(err_msg) from None

        if instance.size is not None and len(instance.size) > 0:
            if instance.size != sku and instance.size != first.model:
                err_msg_lines = [
                    "Instance.size conflicts with accelerator-resolved shape."
                ]
                err_msg_lines.append("INSTANCE: {}".format(instance.name))
                err_msg_lines.append("REQUESTED_SIZE: {}".format(
                    instance.size
                ))
                err_msg_lines.append("RESOLVED_SHAPE: {}".format(sku))
                err_msg = os.linesep.join(err_msg_lines)
                raise OciValidationError(err_msg)

        rtnval = sku
        return rtnval

    def render_user_data(self, *, instance: CloudInstance,
                         authkey: str) -> str:
        """
            Render the cloud-init body (yaml) for the instance.

            :param instance: The CloudInstance.
            :param authkey: Minted auth-key value.

            :returns: A yaml-formatted ``#cloud-config`` body, or "" when
                      no ``vpn_join`` is declared.
        """
        rendered_hostname: Optional[str] = None
        if instance.vpn_join is not None:
            rendered_hostname = instance.vpn_join.hostname_template.replace(
                "{instance_name}", instance.name
            )

        # The shared composer folds VPN join, Python environments and the
        # raw user_data_script into one document.
        document = render_instance_user_data(
            instance=instance, authkey=authkey,
            rendered_hostname=rendered_hostname,
        )
        rtnval = document if document is not None else ""
        return rtnval

    def find(self, *, run_id: str, name: str) -> Optional[Any]:
        """
            Find an existing owned instance by run+name freeform tags.

            :param run_id: Run identifier.
            :param name: Neutral instance name.

            :returns: An OCI Instance model object or None.
        """
        client = self._compute()
        compartment_id = self._session_factory.region_config.compartment_id
        response = list_call_get_all_results(client.list_instances, compartment_id=compartment_id)
        for instance in response.data:
            state = getattr(instance, "lifecycle_state", "")
            if state not in _LIVE_STATES:
                continue
            if matches_resource(entity=instance, run_id=run_id,
                                resource_name=name):
                rtnval: Optional[Any] = instance
                return rtnval
        rtnval = None
        return rtnval

    def ensure(self, *, desired: CloudInstance, run_id: str,
               subnet_id: str, image_id: str,
               authorized_keys: Optional[str],
               cluster_network_id: Optional[str],
               default_tags: List[Dict[str, str]],
               authkey: Optional[str],
               aspects: Any
               ) -> Tuple[ProvisionedResource, Dict[str, Any]]:
        """
            Match-then-act create-or-reuse for a Compute Instance.

            :param desired: Desired CloudInstance.
            :param run_id: Run identifier.
            :param subnet_id: Resolved subnet OCID for the instance.
            :param image_id: Resolved OCI image OCID.
            :param authorized_keys: SSH public key material or None.
            :param cluster_network_id: RDMA cluster network OCID or None.
            :param default_tags: Venue default tags.
            :param authkey: Pre-minted VPN authkey (when vpn_join is set).
            :param aspects: Aspects.

            :returns: (ProvisionedResource, info-dict with vpn_device_id).
        """

        client = self._compute()
        compartment_id = self._session_factory.region_config.compartment_id
        availability_domain = (
            self._session_factory.region_config.availability_domain
        )
        existing = self.find(run_id=run_id, name=desired.name)

        info: Dict[str, Any] = {}

        if existing is not None:
            attributes = self._instance_attributes(existing=existing)
            rtnval_resource = ProvisionedResource(
                kind=self.KIND, name=desired.name,
                venue_id=getattr(existing, "id", ""),
                attributes=attributes,
                tags=from_freeform(
                    freeform_tags=getattr(existing, "freeform_tags", None)
                ),
            )
            info["vpn_device_id"] = None
            rtnval = (rtnval_resource, info)
            return rtnval

        shape = self.resolve_shape(instance=desired)

        user_data_body = self.render_user_data(
            instance=desired,
            authkey=authkey if authkey is not None else "PLACEHOLDER",
        )
        user_data_b64 = ""
        if len(user_data_body) > 0:
            user_data_b64 = base64.b64encode(
                user_data_body.encode("utf-8")
            ).decode("utf-8")

        metadata: Dict[str, str] = {}
        if authorized_keys is not None and len(authorized_keys) > 0:
            metadata["ssh_authorized_keys"] = authorized_keys
        if len(user_data_b64) > 0:
            metadata["user_data"] = user_data_b64

        neutral_tags = base_resource_tags(
            run_id=run_id, resource_name=desired.name,
            resource_kind=self.KIND, extra=dict(desired.tags),
            defaults=default_tags,
        )

        vnic_details = ocimodels.CreateVnicDetails(
            subnet_id=subnet_id,
            assign_public_ip=bool(desired.public_ip),
        )
        source_details = ocimodels.InstanceSourceViaImageDetails(
            image_id=image_id
        )

        launch_kwargs: Dict[str, Any] = {}
        launch_kwargs["compartment_id"] = compartment_id
        launch_kwargs["availability_domain"] = availability_domain
        launch_kwargs["shape"] = shape
        launch_kwargs["display_name"] = "codecraftai-{}-{}".format(
            run_id, desired.name
        )
        launch_kwargs["create_vnic_details"] = vnic_details
        launch_kwargs["source_details"] = source_details
        launch_kwargs["metadata"] = metadata
        launch_kwargs["freeform_tags"] = to_freeform(neutral_tags=neutral_tags)

        if cluster_network_id is not None and len(cluster_network_id) > 0:
            launch_kwargs["compute_cluster_id"] = cluster_network_id

        # Preemption policy → preemptible-instance config.
        policy = desired.preemption_policy
        if isinstance(policy, PreemptionPolicy):
            policy_value = policy.value
        else:
            policy_value = str(policy)

        if policy_value in ("REACQUIRE", "BEST_EFFORT"):
            action = ocimodels.TerminatePreemptionAction(
                type="TERMINATE", preserve_boot_volume=False
            )
            launch_kwargs["preemptible_instance_config"] = (
                ocimodels.PreemptibleInstanceConfigDetails(
                    preemption_action=action
                )
            )

        details = ocimodels.LaunchInstanceDetails(**launch_kwargs)
        created = client.launch_instance(launch_instance_details=details)
        created_instance = created.data

        attributes = self._instance_attributes(existing=created_instance)
        attributes["shape"] = shape
        attributes["image_id"] = image_id
        attributes["preemption_policy"] = policy_value
        if cluster_network_id is not None and len(cluster_network_id) > 0:
            attributes["cluster_network_id"] = cluster_network_id
        if len(user_data_body) > 0:
            attributes["user_data_present"] = True
            attributes["user_data"] = user_data_b64

        rtnval_resource = ProvisionedResource(
            kind=self.KIND, name=desired.name,
            venue_id=getattr(created_instance, "id", ""),
            attributes=attributes,
            tags=from_freeform(
                freeform_tags=getattr(created_instance, "freeform_tags", None)
            ),
        )
        info["vpn_device_id"] = None
        info["user_data_body"] = user_data_body
        rtnval = (rtnval_resource, info)
        return rtnval

    def _instance_attributes(self, *, existing: Any) -> Dict[str, Any]:
        """
            Build the attributes dict for a ProvisionedResource.

            :param existing: OCI Instance model object.

            :returns: Attributes dict.
        """
        out: Dict[str, Any] = {}
        out["instance_id"] = getattr(existing, "id", "")
        out["shape"] = getattr(existing, "shape", "")
        out["state"] = getattr(existing, "lifecycle_state", "")
        out["availability_domain"] = getattr(existing,
                                             "availability_domain", "")
        metadata = getattr(existing, "metadata", None)
        if metadata is not None and isinstance(metadata, dict):
            if "user_data" in metadata:
                out["user_data"] = metadata["user_data"]
        rtnval = out
        return rtnval

    def destroy(self, *, run_id: str, aspects: Any) -> List[Dict[str, Any]]:
        """
            Terminate every owned instance and return per-instance vpn info.

            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of dicts ``{"instance_id", "vpn_device_id",
                      "had_vpn_join"}``.
        """
        client = self._compute()
        compartment_id = self._session_factory.region_config.compartment_id
        records: List[Dict[str, Any]] = []
        response = list_call_get_all_results(client.list_instances, compartment_id=compartment_id)
        for instance in response.data:
            if not belongs_to_run(entity=instance, run_id=run_id):
                continue
            state = getattr(instance, "lifecycle_state", "")
            if state == "TERMINATED":
                continue
            instance_id = getattr(instance, "id", "")
            freeform = getattr(instance, "freeform_tags", None) or {}
            records.append({
                "instance_id": instance_id,
                "vpn_device_id": freeform.get("ccai_vpn-device-id", None),
                "had_vpn_join": freeform.get("ccai_vpn-provider",
                                             None) is not None,
            })
            try:
                client.terminate_instance(instance_id=instance_id)
            except Exception:
                # Best-effort teardown; a failed delete must not stop the remaining
                # resources of the run from being torn down.
                pass
        rtnval = records
        return rtnval

    def list_owned(self, *, run_id: str) -> List[ProvisionedResource]:
        """
            Return every owned instance for the run.

            :param run_id: Run identifier.

            :returns: List of ProvisionedResource entries.
        """
        client = self._compute()
        compartment_id = self._session_factory.region_config.compartment_id
        out: List[ProvisionedResource] = []
        response = list_call_get_all_results(client.list_instances, compartment_id=compartment_id)
        for instance in response.data:
            if not belongs_to_run(entity=instance, run_id=run_id):
                continue
            state = getattr(instance, "lifecycle_state", "")
            if state == "TERMINATED":
                continue
            name = resource_name_of(entity=instance)
            if name is None:
                continue
            attributes = self._instance_attributes(existing=instance)
            entry = ProvisionedResource(
                kind=self.KIND, name=name,
                venue_id=getattr(instance, "id", ""),
                attributes=attributes,
                tags=from_freeform(
                    freeform_tags=getattr(instance, "freeform_tags", None)
                ),
            )
            out.append(entry)
        rtnval = out
        return rtnval
