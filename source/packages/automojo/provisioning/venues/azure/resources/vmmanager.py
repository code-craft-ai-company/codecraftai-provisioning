"""
    .. module:: vmmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Azure Virtual Machine manager — custom-data, IB SKU, PPG, spot.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import base64
import os

from typing import Any, Dict, List, Optional, Tuple

import yaml

from automojo.provisioning.cloudinit.vpncloudinitrenderer import (
    render_azure_cse, render_cloud_init
)
from automojo.provisioning.model.cloud.cloudacceleratorcatalog import (
    CloudAcceleratorCatalog
)
from automojo.provisioning.model.cloud.cloudinstancesizecatalog import (
    CloudInstanceSizeCatalog
)
from automojo.provisioning.model.cloud.cloudinstance import CloudInstance
from automojo.provisioning.model.cloud.preemptionpolicy import PreemptionPolicy
from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.venues.azure.azureerrors import AzureValidationError
from automojo.provisioning.venues.azure.azureidempotency import (
    belongs_to_run, get_or_none
)
from automojo.provisioning.venues.azure.azuresessionfactory import (
    AzureSessionFactory
)
from automojo.provisioning.venues.azure.azuretagging import (
    azure_tags_for, from_azure
)
from automojo.provisioning.venues.azure.azuretask import resolve_poller
from automojo.provisioning.venues.azure.resources.imageresolver import (
    ImageResolver
)
from automojo.provisioning.venues.azure.resources.placement import (
    PlacementManager
)


# Azure VM SKU families that ship with InfiniBand fabric.
_INFINIBAND_FAMILIES = frozenset({
    "Standard_ND96isr_H100_v5",
    "Standard_ND96isr_H200_v5",
    "Standard_ND96isr_B200_v6",
    "Standard_ND96amsr_A100_v4",
    "Standard_ND96isr_MI300X_v5",
    "Standard_NC96ads_A100_v4",
    "Standard_NC40ads_H100_v5",
    "Standard_NC80adis_H100_v5",
})


def is_infiniband_sku(*, vm_size: str) -> bool:
    """
        Return True when an Azure VM SKU ships with InfiniBand.

        :param vm_size: Azure VM size string.

        :returns: True when the SKU is InfiniBand-capable.
    """
    rtnval = vm_size in _INFINIBAND_FAMILIES
    return rtnval


class VmManager:
    """
        Manager for Azure Virtual Machines.

        Wires together:

        - Azure image SKU resolution via :class:`ImageResolver`,
        - GPU SKU resolution via :class:`CloudAcceleratorCatalog`,
        - Proximity Placement Group attachment for InfiniBand SKUs,
        - cloud-init via ``os_profile.custom_data`` (Linux) or a Custom
          Script Extension (Windows),
        - preemption-policy → regular vs spot VMs,
        - tag-based read-before-create for idempotence.
    """

    KIND: str = "instance"
    VENUE_NAME: str = "azure"

    def __init__(self, *, session_factory: AzureSessionFactory,
                 image_resolver: ImageResolver,
                 placement_manager: PlacementManager,
                 catalog: CloudAcceleratorCatalog) -> None:
        """
            Construct a VmManager.

            :param session_factory: AzureSessionFactory.
            :param image_resolver: ImageResolver.
            :param placement_manager: PlacementManager.
            :param catalog: CloudAcceleratorCatalog (for GPU SKU lookup).
        """
        self._session_factory: AzureSessionFactory = session_factory
        self._image_resolver: ImageResolver = image_resolver
        self._placement_manager: PlacementManager = placement_manager
        self._catalog: CloudAcceleratorCatalog = catalog
        return

    def _compute(self) -> Any:
        """
            Return the ComputeManagementClient.

            :returns: A ComputeManagementClient.
        """
        rtnval = self._session_factory.compute_client()
        return rtnval

    def resolve_vm_size(self, *, instance: CloudInstance) -> str:
        """
            Resolve the Azure VM size to launch.

            When ``accelerators`` is set the accelerator catalog is consulted
            with the first accelerator's neutral model; any explicit
            ``size`` must agree with the resolved SKU.  Otherwise ``size``
            is returned verbatim.

            :param instance: The neutral CloudInstance.

            :returns: Azure VM size string.
            :raises: AzureValidationError
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
                "Azure VM accelerator could not be resolved by the catalog."
            ]
            err_msg_lines.append("INSTANCE: {}".format(instance.name))
            err_msg_lines.append("MODEL: {}".format(first.model))
            err_msg_lines.append("CAUSE: {}".format(xcpt))
            err_msg = os.linesep.join(err_msg_lines)
            raise AzureValidationError(err_msg) from None

        if instance.size is not None and len(instance.size) > 0:
            if instance.size != sku and instance.size != first.model:
                err_msg_lines = [
                    "Instance.size conflicts with accelerator-resolved SKU."
                ]
                err_msg_lines.append("INSTANCE: {}".format(instance.name))
                err_msg_lines.append("REQUESTED_SIZE: {}".format(instance.size))
                err_msg_lines.append("RESOLVED_SKU: {}".format(sku))
                err_msg = os.linesep.join(err_msg_lines)
                raise AzureValidationError(err_msg)

        rtnval = sku
        return rtnval

    def render_custom_data(self, *, instance: CloudInstance,
                           authkey: str) -> str:
        """
            Render the cloud-init body for a Linux VM ``custom_data``.

            :param instance: The CloudInstance.
            :param authkey: Minted auth-key value.

            :returns: A ``#cloud-config`` body, or "" when no vpn_join is set.
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

    def render_windows_cse(self, *, instance: CloudInstance,
                           authkey: str) -> Dict[str, Any]:
        """
            Render the Custom Script Extension payload for a Windows VM.

            :param instance: The CloudInstance.
            :param authkey: Minted auth-key value.

            :returns: A dict with ``settings`` / ``protectedSettings`` keys.
        """
        rendered_hostname = instance.vpn_join.hostname_template.replace(
            "{instance_name}", instance.name
        )
        rtnval = render_azure_cse(
            spec=instance.vpn_join, authkey=authkey,
            rendered_hostname=rendered_hostname,
            image_family=instance.image.family,
        )
        return rtnval

    def find(self, *, resource_group: str,
             name: str) -> Optional[Any]:
        """
            Find an existing owned VM by name.

            :param resource_group: ResourceGroup name.
            :param name: Neutral instance name.

            :returns: The VirtualMachine object, or None.
        """
        client = self._compute()
        rtnval = get_or_none(getter=client.virtual_machines.get,
                             resource_group_name=resource_group,
                             vm_name=name)
        return rtnval

    def ensure(self, *, desired: CloudInstance, resource_group: str,
               location: str, run_id: str, nic_id: str,
               admin_public_key: Optional[str],
               default_tags: List[Dict[str, str]],
               authkey: Optional[str],
               aspects: Any
               ) -> Tuple[ProvisionedResource, Dict[str, Any]]:
        """
            Match-then-act create-or-reuse for an Azure VM.

            :param desired: Desired CloudInstance.
            :param resource_group: ResourceGroup name.
            :param location: Azure location.
            :param run_id: Run identifier.
            :param nic_id: Azure NIC resource id for the VM.
            :param admin_public_key: OpenSSH public-key material, or None.
            :param default_tags: Venue default tags.
            :param authkey: Pre-minted VPN authkey (when vpn_join is set).
            :param aspects: Aspects.

            :returns: (ProvisionedResource, info-dict including
                      ``vpn_device_id`` and ``custom_data``).
        """
        client = self._compute()
        existing = self.find(resource_group=resource_group,
                             name=desired.name)
        info: Dict[str, Any] = {}

        if existing is not None:
            attributes = self._vm_attributes(existing=existing)
            info["vpn_device_id"] = None
            rtnval_resource = ProvisionedResource(
                kind=self.KIND, name=desired.name,
                venue_id=getattr(existing, "id", desired.name),
                attributes=attributes,
                tags=from_azure(azure_tags=getattr(existing, "tags", None)),
            )
            rtnval = (rtnval_resource, info)
            return rtnval

        vm_size = self.resolve_vm_size(instance=desired)
        image_ref = self._image_resolver.image_reference(image=desired.image)
        is_windows = desired.image.family == "windows-server"

        # OS profile.
        os_profile: Dict[str, Any] = {
            "computer_name": desired.name,
            "admin_username": "azureuser",
        }

        custom_data_body = ""
        cse_payload: Optional[Dict[str, Any]] = None
        effective_authkey = authkey if authkey is not None else "PLACEHOLDER"

        if is_windows:
            os_profile["admin_password"] = "Azur3-{}-Pa55!".format(run_id[:8])
            if desired.vpn_join is not None:
                cse_payload = self.render_windows_cse(
                    instance=desired, authkey=effective_authkey
                )
        else:
            linux_config: Dict[str, Any] = {
                "disable_password_authentication": True,
            }
            if admin_public_key is not None and len(admin_public_key) > 0:
                linux_config["ssh"] = {
                    "public_keys": [{
                        "path": "/home/azureuser/.ssh/authorized_keys",
                        "key_data": admin_public_key,
                    }],
                }
            os_profile["linux_configuration"] = linux_config

            custom_data_body = self.render_custom_data(
                instance=desired, authkey=effective_authkey
            )
            if len(custom_data_body) > 0:
                os_profile["custom_data"] = base64.b64encode(
                    custom_data_body.encode("utf-8")
                ).decode("utf-8")

        tags = azure_tags_for(run_id=run_id, resource_name=desired.name,
                              resource_kind=self.KIND,
                              extra=dict(desired.tags),
                              defaults=default_tags)

        params: Dict[str, Any] = {
            "location": location,
            "hardware_profile": {"vm_size": vm_size},
            "storage_profile": {"image_reference": image_ref},
            "os_profile": os_profile,
            "network_profile": {
                "network_interfaces": [{"id": nic_id, "primary": True}],
            },
            "tags": tags,
        }

        # InfiniBand SKUs land in a Proximity Placement Group.
        ppg_id: Optional[str] = None
        if is_infiniband_sku(vm_size=vm_size):
            logical = desired.placement_group
            if logical is None or len(logical) == 0:
                logical = "{}-ib".format(run_id)
            ppg_id = self._placement_manager.ensure(
                logical_name=logical, resource_group=resource_group,
                location=location, run_id=run_id,
                default_tags=default_tags, aspects=aspects,
            )
            params["proximity_placement_group"] = {"id": ppg_id}

        # Preemption policy → spot VMs.
        policy = desired.preemption_policy
        if isinstance(policy, PreemptionPolicy):
            policy_value = policy.value
        else:
            policy_value = str(policy)

        if policy_value in ("REACQUIRE", "BEST_EFFORT"):
            params["priority"] = "Spot"
            params["eviction_policy"] = "Deallocate"
            params["billing_profile"] = {"max_price": -1.0}

        poller = client.virtual_machines.begin_create_or_update(
            resource_group_name=resource_group, vm_name=desired.name,
            parameters=params,
        )
        created = resolve_poller(poller=poller, aspects=aspects,
                                 description="create vm {}".format(
                                     desired.name
                                 ))

        # Windows VPN-join uses a Custom Script Extension applied post-create.
        if cse_payload is not None:
            try:
                ext_params: Dict[str, Any] = {
                    "location": location,
                    "publisher": "Microsoft.Compute",
                    "type_properties_type": "CustomScriptExtension",
                    "type_handler_version": "1.10",
                    "settings": cse_payload.get("settings", {}),
                    "protected_settings": cse_payload.get(
                        "protectedSettings", {}
                    ),
                }
                ext_poller = client.virtual_machine_extensions.begin_create_or_update(
                    resource_group_name=resource_group,
                    vm_name=desired.name,
                    vm_extension_name="{}-vpncse".format(desired.name),
                    extension_parameters=ext_params,
                )
                resolve_poller(poller=ext_poller, aspects=aspects,
                               description="cse {}".format(desired.name))
            except Exception:
                pass

        attributes = self._vm_attributes(existing=created)
        attributes["vm_size"] = vm_size
        attributes["preemption_policy"] = policy_value
        attributes["image_sku"] = image_ref.get("sku", "")
        if ppg_id is not None:
            attributes["proximity_placement_group_id"] = ppg_id
        if len(custom_data_body) > 0:
            attributes["custom_data_present"] = True

        rtnval_resource = ProvisionedResource(
            kind=self.KIND, name=desired.name,
            venue_id=getattr(created, "id", desired.name),
            attributes=attributes,
            tags=from_azure(azure_tags=getattr(created, "tags", None)),
        )
        info["vpn_device_id"] = None
        info["custom_data"] = custom_data_body
        info["cse_payload"] = cse_payload
        rtnval = (rtnval_resource, info)
        return rtnval

    def _vm_attributes(self, *, existing: Any) -> Dict[str, Any]:
        """
            Build the attributes dict for a ProvisionedResource.

            :param existing: The live VirtualMachine object.

            :returns: Attributes dict.
        """
        out: Dict[str, Any] = {}
        out["vm_name"] = getattr(existing, "name", "")
        hardware = getattr(existing, "hardware_profile", None)
        if hardware is not None:
            out["vm_size"] = getattr(hardware, "vm_size", "")
        out["provisioning_state"] = getattr(existing,
                                            "provisioning_state", "")
        out["priority"] = getattr(existing, "priority", "")
        rtnval = out
        return rtnval

    def destroy(self, *, resource_group: str,
                run_id: str, aspects: Any) -> List[Dict[str, Any]]:
        """
            Destroy every owned VM in the ResourceGroup for the run.

            :param resource_group: ResourceGroup name.
            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of dicts ``{"vm_name", "vpn_device_id",
                      "had_vpn_join"}``.
        """
        client = self._compute()
        records: List[Dict[str, Any]] = []
        try:
            listing = list(client.virtual_machines.list(
                resource_group_name=resource_group
            ))
        except Exception:
            rtnval = records
            return rtnval

        for vm in listing:
            live_tags = getattr(vm, "tags", None)
            if not belongs_to_run(azure_tags=live_tags, run_id=run_id):
                continue
            vm_name = getattr(vm, "name", "")
            flat = live_tags if isinstance(live_tags, dict) else {}
            records.append({
                "vm_name": vm_name,
                "vpn_device_id": flat.get("automojo:vpn-device-id", None),
                "had_vpn_join": flat.get("automojo:vpn-provider",
                                         None) is not None,
            })
            try:
                client.virtual_machines.begin_delete(
                    resource_group_name=resource_group, vm_name=vm_name
                )
            except Exception:
                pass

        rtnval = records
        return rtnval

    def list_owned(self, *, resource_group: str,
                   run_id: str) -> List[ProvisionedResource]:
        """
            Return every owned VM in the ResourceGroup for the run.

            :param resource_group: ResourceGroup name.
            :param run_id: Run identifier.

            :returns: List of ProvisionedResource entries.
        """
        client = self._compute()
        out: List[ProvisionedResource] = []
        try:
            listing = list(client.virtual_machines.list(
                resource_group_name=resource_group
            ))
        except Exception:
            rtnval = out
            return rtnval

        for vm in listing:
            live_tags = getattr(vm, "tags", None)
            if not belongs_to_run(azure_tags=live_tags, run_id=run_id):
                continue
            attributes = self._vm_attributes(existing=vm)
            out.append(ProvisionedResource(
                kind=self.KIND, name=getattr(vm, "name", ""),
                venue_id=getattr(vm, "id", getattr(vm, "name", "x")),
                attributes=attributes,
                tags=from_azure(azure_tags=live_tags),
            ))

        rtnval = out
        return rtnval
