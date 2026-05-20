"""
    .. module:: instancemanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: GCP Compute Engine instance manager — user-data, GPU SKU,
               compact placement, preemption.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Optional, Tuple

import yaml

from automojo.provisioning.cloudinit.vpncloudinitrenderer import (
    render_cloud_init
)
from automojo.provisioning.model.cloud.cloudacceleratorcatalog import (
    CloudAcceleratorCatalog
)
from automojo.provisioning.model.cloud.cloudimage import CloudImage
from automojo.provisioning.model.cloud.cloudinstance import CloudInstance
from automojo.provisioning.model.cloud.preemptionpolicy import PreemptionPolicy
from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.venues.google.gcperrors import GcpValidationError
from automojo.provisioning.venues.google.gcpsessionfactory import (
    GcpSessionFactory, SERVICE_COMPUTE
)
from automojo.provisioning.venues.google.gcpidempotency import (
    belongs_to_run
)
from automojo.provisioning.venues.google.gcptagging import (
    base_resource_labels, from_labels, RESOURCE_NAME_LABEL_KEY
)


# Neutral image family → GCP image family resolution table.
_IMAGE_FAMILY_TABLE: Dict[str, Tuple[str, str]] = {
    "ubuntu": ("ubuntu-os-cloud", "ubuntu-{version}-lts"),
    "debian": ("debian-cloud", "debian-{version}"),
    "rhel": ("rhel-cloud", "rhel-{version}"),
    "windows-server": ("windows-cloud", "windows-{version}"),
}

# GCP machine families that support compact placement for A3 training.
_A3_FAMILY_MACHINE_TYPES = frozenset({
    "a3-highgpu-8g", "a3-megagpu-8g", "a3-ultragpu-8g",
})


def resolve_image_uri(*, image: CloudImage) -> str:
    """
        Resolve a neutral CloudImage to a GCP image-family resource URI.

        :param image: The neutral CloudImage.

        :returns: A ``projects/.../global/images/family/...`` URI.
        :raises: GcpValidationError
    """
    entry = _IMAGE_FAMILY_TABLE.get(image.family, None)
    if entry is None:
        err_msg_lines = ["Image family is not resolvable on GCP."]
        err_msg_lines.append("FAMILY: {!r}".format(image.family))
        err_msg_lines.append(
            "KNOWN: {}".format(", ".join(sorted(_IMAGE_FAMILY_TABLE.keys())))
        )
        err_msg = os.linesep.join(err_msg_lines)
        raise GcpValidationError(err_msg)

    project, family_template = entry
    version_token = image.version.replace(".", "")
    family = family_template.replace("{version}", version_token)
    rtnval = "projects/{}/global/images/family/{}".format(project, family)
    return rtnval


def is_a3_machine_type(*, machine_type: str) -> bool:
    """
        Return True when the machine type is an A3-family compact-capable SKU.

        :param machine_type: GCP machine type string.

        :returns: True when the machine type supports compact placement.
    """
    rtnval = machine_type in _A3_FAMILY_MACHINE_TYPES
    return rtnval


class InstanceManager:
    """
        Manager for GCP Compute Engine instances.

        Wires together:

        - cloud-init render into ``metadata.items["user-data"]``,
        - GPU SKU resolution via :class:`CloudAcceleratorCatalog`,
        - compact-placement ResourcePolicy attachment,
        - preemption-policy → spot / preemptible VMs,
        - label-based read-before-create for idempotence.
    """

    KIND: str = "instance"
    VENUE_NAME: str = "gcp"

    def __init__(self, *, session_factory: GcpSessionFactory,
                 catalog: CloudAcceleratorCatalog) -> None:
        """
            Construct an InstanceManager.

            :param session_factory: GcpSessionFactory.
            :param catalog: CloudAcceleratorCatalog (for GPU SKU lookup).
        """
        self._session_factory: GcpSessionFactory = session_factory
        self._catalog: CloudAcceleratorCatalog = catalog
        return

    def _client(self) -> Any:
        """
            Return the compute ``instances`` sub-client.

            :returns: The instances sub-client.
        """
        compute = self._session_factory.client(service_name=SERVICE_COMPUTE)
        rtnval = compute["instances"]
        return rtnval

    def _gcp_name(self, *, run_id: str, name: str) -> str:
        """
            Build the GCP-side instance name.

            :param run_id: Run identifier.
            :param name: Neutral instance name.

            :returns: A GCP-conformant instance name.
        """
        rtnval = "automojo-{}-{}".format(run_id, name).lower()
        return rtnval

    def resolve_machine_type(self, *, instance: CloudInstance) -> str:
        """
            Resolve the GCP machine type to launch.

            When ``accelerators`` is set with a GPU model, the catalog SKU is
            used; the user-supplied ``size`` must agree.  Otherwise ``size``
            is returned verbatim.

            :param instance: The neutral CloudInstance.

            :returns: GCP machine-type string.
            :raises: GcpValidationError
        """
        accelerators = (
            instance.accelerators if instance.accelerators is not None else []
        )
        gpu_accels = [a for a in accelerators if a.kind == "GPU"]
        if len(gpu_accels) == 0:
            rtnval = instance.size
            return rtnval

        first = gpu_accels[0]
        try:
            sku = self._catalog.resolve(neutral_name=first.model,
                                        venue=self.VENUE_NAME)
        except Exception as xcpt:
            err_msg_lines = [
                "GCP instance accelerator could not be resolved by the catalog."
            ]
            err_msg_lines.append("INSTANCE: {}".format(instance.name))
            err_msg_lines.append("MODEL: {}".format(first.model))
            err_msg_lines.append("CAUSE: {}".format(xcpt))
            err_msg = os.linesep.join(err_msg_lines)
            raise GcpValidationError(err_msg) from None

        if instance.size is not None and len(instance.size) > 0:
            if instance.size != sku and instance.size != first.model:
                err_msg_lines = [
                    "Instance.size conflicts with accelerator-resolved SKU."
                ]
                err_msg_lines.append("INSTANCE: {}".format(instance.name))
                err_msg_lines.append("REQUESTED_SIZE: {}".format(instance.size))
                err_msg_lines.append("RESOLVED_SKU: {}".format(sku))
                err_msg = os.linesep.join(err_msg_lines)
                raise GcpValidationError(err_msg)

        rtnval = sku
        return rtnval

    def render_user_data(self, *, instance: CloudInstance,
                         authkey: str) -> str:
        """
            Render the cloud-init body (yaml) for the instance.

            :param instance: The CloudInstance.
            :param authkey: Minted auth-key value.

            :returns: A yaml-formatted ``#cloud-config`` body, or "" when no
                      ``vpn_join`` is declared.
        """
        if instance.vpn_join is None:
            base_script = instance.user_data_script
            rtnval = base_script if base_script is not None else ""
            return rtnval

        rendered_hostname = instance.vpn_join.hostname_template.replace(
            "{instance_name}", instance.name
        )
        cloud_init = render_cloud_init(
            spec=instance.vpn_join,
            authkey=authkey,
            rendered_hostname=rendered_hostname,
            image_family=instance.image.family,
        )

        body_lines: List[str] = ["#cloud-config"]
        body_lines.append(yaml.safe_dump(cloud_init, sort_keys=False))
        rtnval = "\n".join(body_lines)
        return rtnval

    def find(self, *, run_id: str, name: str,
             zone: str) -> Optional[Dict[str, Any]]:
        """
            Find an existing owned instance by run+name labels.

            :param run_id: Run identifier.
            :param name: Neutral instance name.
            :param zone: Zone the instance lives in.

            :returns: An instance resource dict or None.
        """
        client = self._client()
        project = self._session_factory.project
        gcp_name = self._gcp_name(run_id=run_id, name=name)
        existing = client.get(project=project, zone=zone,
                              instance=gcp_name)
        if existing is None:
            rtnval: Optional[Dict[str, Any]] = None
            return rtnval
        if not belongs_to_run(labels=existing.get("labels", {}),
                              run_id=run_id):
            rtnval = None
            return rtnval
        rtnval = existing
        return rtnval

    def ensure(self, *, desired: CloudInstance, run_id: str, zone: str,
               subnet_self_link: str, network_self_link: str,
               default_tags: List[Dict[str, str]],
               authkey: Optional[str],
               placement_policy_name: Optional[str],
               region: str,
               aspects: Any
               ) -> Tuple[ProvisionedResource, Dict[str, Any]]:
        """
            Match-then-act create-or-reuse for a Compute Engine instance.

            :param desired: Desired CloudInstance.
            :param run_id: Run identifier.
            :param zone: Zone to launch in.
            :param subnet_self_link: Resolved subnetwork self-link.
            :param network_self_link: Resolved VPC network self-link.
            :param default_tags: Venue default tags.
            :param authkey: Pre-minted VPN authkey (when vpn_join is set).
            :param placement_policy_name: Optional compact-placement policy.
            :param region: GCP region (for resource-policy reference).
            :param aspects: Aspects.

            :returns: (ProvisionedResource, info-dict).
        """
        client = self._client()
        project = self._session_factory.project
        gcp_name = self._gcp_name(run_id=run_id, name=desired.name)

        info: Dict[str, Any] = {}

        existing = self.find(run_id=run_id, name=desired.name, zone=zone)
        if existing is not None:
            attributes = self._instance_attributes(existing=existing,
                                                    zone=zone)
            resource = ProvisionedResource(
                kind=self.KIND, name=desired.name, venue_id=gcp_name,
                attributes=attributes,
                tags=from_labels(labels=existing.get("labels", {})),
            )
            info["vpn_device_id"] = None
            rtnval = (resource, info)
            return rtnval

        machine_type = self.resolve_machine_type(instance=desired)
        image_uri = resolve_image_uri(image=desired.image)
        labels = base_resource_labels(
            run_id=run_id, resource_name=desired.name,
            resource_kind=self.KIND, extra=list(desired.tags),
            defaults=default_tags,
        )

        user_data_body = self.render_user_data(
            instance=desired,
            authkey=authkey if authkey is not None else "PLACEHOLDER",
        )
        metadata_items: List[Dict[str, str]] = []
        if len(user_data_body) > 0:
            metadata_items.append({"key": "user-data",
                                   "value": user_data_body})

        # SSH key metadata when a keypair is present (OS Login bypassed).
        ssh_public_key = info.get("ssh_public_key", None)

        body: Dict[str, Any] = {
            "name": gcp_name,
            "machine_type": "zones/{}/machineTypes/{}".format(
                zone, machine_type
            ),
            "labels": labels,
            "disks": [{
                "boot": True,
                "auto_delete": True,
                "initialize_params": {"source_image": image_uri},
            }],
            "network_interfaces": [{
                "network": network_self_link,
                "subnetwork": subnet_self_link,
            }],
            "metadata": {"items": list(metadata_items)},
        }

        if bool(desired.public_ip) is True:
            body["network_interfaces"][0]["access_configs"] = [
                {"name": "External NAT", "type": "ONE_TO_ONE_NAT"}
            ]

        # GPU guest accelerators.
        accelerators = (
            desired.accelerators if desired.accelerators is not None else []
        )
        gpu_accels = [a for a in accelerators if a.kind == "GPU"]
        if len(gpu_accels) > 0:
            first = gpu_accels[0]
            body["guest_accelerators"] = [{
                "accelerator_type": "zones/{}/acceleratorTypes/{}".format(
                    zone, machine_type
                ),
                "accelerator_count": first.count,
            }]

        # Compact placement ResourcePolicy.
        if placement_policy_name is not None:
            policy_link = (
                "projects/{}/regions/{}/resourcePolicies/{}".format(
                    project, region, placement_policy_name
                )
            )
            body["resource_policies"] = [policy_link]

        # Preemption policy → spot / preemptible scheduling.
        policy = desired.preemption_policy
        if isinstance(policy, PreemptionPolicy):
            policy_value = policy.value
        else:
            policy_value = str(policy)

        if policy_value in ("REACQUIRE", "BEST_EFFORT"):
            body["scheduling"] = {
                "preemptible": True,
                "provisioning_model": "SPOT",
                "automatic_restart": False,
            }
        else:
            body["scheduling"] = {
                "preemptible": False,
                "provisioning_model": "STANDARD",
            }

        client.insert(project=project, zone=zone, instance_resource=body)
        created = client.get(project=project, zone=zone, instance=gcp_name)
        if created is None:
            created = body

        attributes = self._instance_attributes(existing=created, zone=zone)
        attributes["machine_type"] = machine_type
        attributes["image_uri"] = image_uri
        attributes["preemption_policy"] = policy_value
        if placement_policy_name is not None:
            attributes["placement_policy"] = placement_policy_name
        if len(user_data_body) > 0:
            attributes["user_data_present"] = True

        resource = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=gcp_name,
            attributes=attributes,
            tags=from_labels(labels=created.get("labels", labels)),
        )
        info["vpn_device_id"] = None
        info["user_data_body"] = user_data_body
        rtnval = (resource, info)
        return rtnval

    def _instance_attributes(self, *, existing: Dict[str, Any],
                             zone: str) -> Dict[str, Any]:
        """
            Build the attributes dict for a ProvisionedResource.

            :param existing: GCP instance resource dict.
            :param zone: Zone the instance lives in.

            :returns: Attributes dict.
        """
        out: Dict[str, Any] = {}
        out["instance_id"] = str(existing.get("id", existing.get("name", "")))
        out["gcp_name"] = existing.get("name", "")
        out["zone"] = zone
        out["status"] = existing.get("status", "")

        private_ip = ""
        public_ip = ""
        for nic in existing.get("network_interfaces", []):
            if len(private_ip) == 0:
                private_ip = nic.get("network_i_p", nic.get("network_ip", ""))
            for access in nic.get("access_configs", []):
                if len(public_ip) == 0:
                    public_ip = access.get("nat_i_p",
                                           access.get("nat_ip", ""))
        out["private_ip"] = private_ip
        out["public_ip"] = public_ip
        rtnval = out
        return rtnval

    def destroy(self, *, run_id: str, zone: str,
                aspects: Any) -> List[Dict[str, Any]]:
        """
            Delete every owned instance in the zone for the run.

            :param run_id: Run identifier.
            :param zone: Zone to scan.
            :param aspects: Aspects.

            :returns: List of per-instance records.
        """
        client = self._client()
        project = self._session_factory.project
        records: List[Dict[str, Any]] = []
        for entry in self.list_raw(run_id=run_id, zone=zone):
            gcp_name = entry.get("name", "")
            if len(gcp_name) == 0:
                continue
            labels = entry.get("labels", {})
            records.append({
                "instance_name": gcp_name,
                "vpn_device_id": labels.get("automojo_vpn-device-id", None),
            })
            try:
                client.delete(project=project, zone=zone,
                              instance=gcp_name)
            except Exception:
                pass
        rtnval = records
        return rtnval

    def list_raw(self, *, run_id: str,
                 zone: str) -> List[Dict[str, Any]]:
        """
            Return raw owned instance resource dicts for the run.

            :param run_id: Run identifier.
            :param zone: Zone to scan.

            :returns: List of instance resource dicts.
        """
        client = self._client()
        project = self._session_factory.project
        out: List[Dict[str, Any]] = []
        for entry in client.list(project=project, zone=zone):
            if belongs_to_run(labels=entry.get("labels", {}),
                              run_id=run_id):
                out.append(entry)
        rtnval = out
        return rtnval

    def list_owned(self, *, run_id: str,
                   zone: str) -> List[ProvisionedResource]:
        """
            Return every owned instance for the run as ProvisionedResources.

            :param run_id: Run identifier.
            :param zone: Zone to scan.

            :returns: List of ProvisionedResource entries.
        """
        out: List[ProvisionedResource] = []
        for entry in self.list_raw(run_id=run_id, zone=zone):
            labels = entry.get("labels", {})
            name = labels.get(RESOURCE_NAME_LABEL_KEY, "")
            if len(name) == 0:
                continue
            attributes = self._instance_attributes(existing=entry, zone=zone)
            resource = ProvisionedResource(
                kind=self.KIND, name=name,
                venue_id=entry.get("name", ""),
                attributes=attributes,
                tags=from_labels(labels=labels),
            )
            out.append(resource)
        rtnval = out
        return rtnval
