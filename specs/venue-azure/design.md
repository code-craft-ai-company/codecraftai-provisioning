# Design — Azure Cloud Provisioner

## Overview

`AzureCloudProvisioner` realises the neutral resource model on Microsoft Azure.  The
distinguishing structural choice for Azure is the explicit `ResourceGroup`: this
provisioner treats the ResourceGroup as the apex container for an `apod`'s resources
and uses the run-id as the tag scope inside it.  All ARM/SDK calls flow through
`codecraftai-interop-azure`'s `AzureClient`, which wraps `azure-identity` +
`azure-mgmt-resource` + the per-service `azure-mgmt-*` SDKs.

The implementation follows the §2.7.3 pipeline.  GPU/RDMA support is realised by
choosing NDv5 / NCv4 SKUs and creating Proximity Placement Groups; shared FS is
realised by Azure Managed Lustre or Azure NetApp Files attach-only in v1.

See Also:
- [cloud-resource-model](../cloud-resource-model/design.md)
- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md)
- [vpn-join-spec](../vpn-join-spec/design.md)
- [azure-credentials](../../../codecraftai-credentials/specs/azure-credentials/design.md)
- `codecraftai-interop-azure/Agents.md`

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│           ProvisioningEngine                                 │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                  AzureCloudProvisioner                       │
│  provisioning/venues/azure/azurecloudprovisioner.py          │
└────┬──────────────────┬───────────────────┬─────────────────┘
     │                  │                   │
     ▼                  ▼                   ▼
┌─────────────┐ ┌────────────────┐  ┌──────────────────────┐
│AzureResolver│ │AzureTagTranslator│ │AzureCustomDataRenderer│
│sku/img/accel│ │ neutral↔dict     │ │ user_data / extension │
└─────────────┘ └────────────────┘  └──────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                AzureClient (codecraftai-interop-azure)          │
│   resource / network / compute / storage / dns / lustre      │
│   azure-mgmt-* SDK calls                                     │
└──────────────────────────────────────────────────────────────┘
```

ARM call paths used by `apply`:

- `resource.resource_groups.get` / `create_or_update`
- `network.virtual_networks.get` / `begin_create_or_update`
- `network.subnets.get` / `begin_create_or_update`
- `network.network_security_groups.get` / `begin_create_or_update`
- `network.network_interfaces.get` / `begin_create_or_update`
- `compute.virtual_machines.get` / `begin_create_or_update` (with `custom_data`)
- `compute.disks.get` / `begin_create_or_update`
- `compute.proximity_placement_groups.get` / `create_or_update` for IB SKUs
- `storage.storage_accounts.create` / `blob_containers.create`
- `dns.record_sets.create_or_update`
- `storagecache.amlfilesystems.get` / `mount_targets` for Managed Lustre

All long-running ARM calls expose `LROPoller`; the venue's apply stages call
`.result(timeout=aspects.timeout_seconds)`.

---

## Mapping Table

| Neutral model | Azure resource | Notes |
| --- | --- | --- |
| `apod` envelope | ResourceGroup | One RG per apod; tagged with run-id. |
| `CloudNetwork` | VNet | `cidr` → `address_space.address_prefixes`. |
| `CloudSubnet` | Subnet | `cidr` → `address_prefix`. |
| `CloudSecurityGroup` | NSG + `security_rules` | priorities auto-assigned starting at 1000. |
| `CloudKeyPair` | (no native resource) | Injected into VM `os_profile.linux_configuration.ssh.public_keys`. |
| `CloudImage` | URN | `family="ubuntu",version="24.04"` → `Canonical:0001-com-ubuntu-server-noble:24_04-lts-gen2:latest`. |
| `CloudInstance` | VirtualMachine + NIC | `size` → `vm_size`; `vpn_join` → `custom_data` (base64). |
| `CloudInstance.accelerators` | NDv5 / NCv4 SKU | resolved by `AzureResolver`. |
| `CloudInterconnect(INFINIBAND_NDR)` | NDv5 SKU + Proximity Placement Group | placement group named `<apod>-ppg`. |
| `CloudStorageVolume` | Managed Disk | `type` → `Premium_LRS` / `StandardSSD_LRS`. |
| `CloudObjectBucket` | Storage Account + Blob Container | account name DNS-safe; suffix from run-id. |
| `CloudLoadBalancer` | Azure Load Balancer (v1.5 stub) | `validate`-errors today. |
| `CloudDnsRecord` | Azure DNS record set | zone resolved by `zone_name`. |
| `CloudSharedFilesystem(LUSTRE)` | Azure Managed Lustre | attach-only; `existing_id` required. |
| `CloudSharedFilesystem(AZUREFILES)` | ANF volume | attach-only; mount via NFSv4.1. |
| `VPNJoinSpec` (Linux) | cloud-init `runcmd` in `custom_data` | base64-encoded. |
| `VPNJoinSpec` (Windows) | Custom Script Extension | runs `Install-Tailscale.ps1` from a known URI. |
| Tags | `Dict[str,str]` on every resource | collision-free required. |

---

## Module Layout

```
source/packages/ccai/provisioning/venues/azure/
├── __init__.py
├── azurecloudprovisioner.py
├── azureresolver.py             # image URN / VM size / accelerator → SKU
├── azuretagtranslator.py        # neutral List[Dict] ↔ Azure Dict
├── azurecustomdatarenderer.py   # user_data → base64 custom_data, or CSE
├── azureplanbuilder.py
├── azureapplystages.py
├── azuredestroystages.py
├── azureinventory.py
└── azureerrors.py
```

---

## Data Models

```python
@dataclass
class AzureApplyResult:
    run_id: str
    resource_group: str
    created: list[ProvisionedResource]
    updated: list[ProvisionedResource]
    skipped: list[ProvisionedResource]
    failed: list[ProvisioningError]
```

---

## Idempotency

The ResourceGroup is the primary tag scope.  Every resource read uses a `.get(...)`
that returns `None` (after catching `ResourceNotFoundError`) when absent.  Mutating
calls are skipped when the live resource's `tags["codecraftai-run-id"]` matches the spec
and mutable attributes are equal.  VM SKU changes are treated as UPDATE-by-recreate
because Azure does not permit resize across families with attached disks; the
recreate is gated on `aspects.confirm`.

---

## Testing Strategy

- Mock `AzureClient` with deterministic `get` / `begin_create_or_update` shims.
- Property tests cover idempotent apply, inverse destroy, and tag round-trip
  identity (collision-free generators).
- Resolver tables are unit-tested for every documented neutral image family →
  Azure URN, and every neutral accelerator → NDv5/NCv4 SKU.
- A Proximity Placement Group test verifies that multiple IB-requesting VMs in the
  same `interconnect_group` land in the same PPG.
- Live Azure runs gated by `RUN_LIVE_AZURE=1`.
