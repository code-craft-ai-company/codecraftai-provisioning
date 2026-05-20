# Design — VSphere Provisioner

## Overview

`VSphereCloudProvisioner` realises the neutral resource model on VMware vSphere
through the rebuilt `VSphereClient` in `automojo-interop-vsphere` (PLAN §6.2;
IMPLEMENTATION-PLAN §1.15).  It assumes the post-extraction client shape: REST
on `RestClientBase`, `RestApiGroup`-backed api groups, `VSphereTaskHandle`
returned by every async op, `Aspects`-controlled `wait`.

vSphere is the reference VM-hypervisor venue.  Its honest-fit boundaries are
documented in §6.3 of the plan and surfaced in `validate`:

- no native object storage → `CloudObjectBucket` is a `validate`-error
- no native LB without NSX → `CloudLoadBalancer` `validate`-errors when NSX is
  absent (and composes `automojo-interop-nsx` when present)
- no HPC interconnect → `CloudInterconnect(kind != NONE)` `validate`-errors
- shared FS via NFS datastore attach only — provisioning new managed Lustre is
  out of scope

See Also:
- [cloud-resource-model](../cloud-resource-model/design.md)
- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md)
- [vpn-join-spec](../vpn-join-spec/design.md)
- `automojo-interop-vsphere/Agents.md` and
  `automojo-interop-vsphere/specs/vsphere-client/design.md`

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    ProvisioningEngine                        │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              VSphereCloudProvisioner                         │
│  provisioning/venues/vsphere/vspherecloudprovisioner.py      │
└────┬───────────────────┬────────────────────┬───────────────┘
     │                   │                    │
     ▼                   ▼                    ▼
┌─────────────┐  ┌──────────────────┐  ┌──────────────────────┐
│VsResolver   │  │VsTagTranslator   │  │VsGuestCustomRender   │
│img/tmpl/ds  │  │ cat+tag round-tr │  │  cloud-init/sysprep  │
└─────────────┘  └──────────────────┘  └──────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│        VSphereClient (automojo-interop-vsphere)              │
│   Network / Content / Vm / Cluster / DataStore / Tagging /   │
│   Folder / Host  apigroups on RestClientBase                 │
│   Returns VSphereTaskHandle for async ops                    │
└──────────────────────────────────────────────────────────────┘
```

REST call paths used by `apply` (against vCenter REST 7/8):

- `Network.list` / `Network.create` for DVS / Port Group
- `Content.Library.Item.find` (by tag) and `Content.OvfLibraryItem.deploy`
  for template clone
- `Vm.list` / `Vm.create` (VmCreateSpec) when not library-backed
- `Vm.Hardware.Disk.create` for additional disks
- `Vm.guest_customization.set` for hostname/IP/DNS/SSH-key/cloud-init
- `Vm.Power.start` / `stop`
- `Tagging.Category.list` / `create` and `Tagging.Tag.list` / `create` /
  `attach`

All async ops return `VSphereTaskHandle`; the provisioner calls
`handle.wait(aspects=aspects)` immediately to keep the sync-with-Aspects model
documented in PLAN §6.6.

---

## Mapping Table

| Neutral model | vSphere primitive | Notes |
| --- | --- | --- |
| `CloudNetwork` | Distributed Virtual Switch | one DVS per neutral network (or reuse named). |
| `CloudSubnet` | Distributed Port Group | VLAN id + IPAM-range hint stored in tag. |
| `CloudSecurityGroup` | NSX SG (NSX present) or port-group ACL hint | honest warning when NSX absent. |
| `CloudKeyPair` | injected into guest customisation `users.ssh_authorized_keys` | no first-class resource. |
| `CloudImage` | Content Library item OR named VM template | library lookup first. |
| `CloudInstance` | VM (clone-from-library or create-from-spec) | `size` → CPU/RAM via `vmhardware.py`. |
| `CloudInstance.accelerators` | vGPU profile (when configured) | partial — most lab installs lack vGPU. |
| `CloudInterconnect` | unsupported | `validate`-error for non-`NONE`. |
| `CloudStorageVolume` | VMDK on selected datastore | datastore via `find_datastore_with_free_gb`. |
| `CloudObjectBucket` | unsupported | `validate`-error. |
| `CloudLoadBalancer` | NSX LB (when NSX present) | else `validate`-error. |
| `CloudDnsRecord` | external (out of vCenter) | warn today. |
| `CloudSharedFilesystem(*, existing_id)` | NFS datastore mount | attach-only. |
| `VPNJoinSpec` | guest customisation cloud-init `runcmd` | identical pattern to AWS user_data. |
| Tags | vSphere Categories + Tags | round-trip identity. |

---

## Module Layout

```
source/packages/automojo/provisioning/venues/vsphere/
├── __init__.py
├── vspherecloudprovisioner.py
├── vsresolver.py                  # library-item / template / datastore resolution
├── vstagtranslator.py             # neutral ↔ category+tag
├── vsguestcustomrenderer.py       # cloud-init / sysprep
├── vsplanbuilder.py
├── vsapplystages.py
├── vsdestroystages.py
├── vsinventory.py
└── vserrors.py
```

---

## Idempotency

Reads filter by attached category-tag pair (`automojo-run-id=<id>`).  VM hardware
deltas honour vSphere's reconfigure rules: CPU/RAM hot-add when the guest
supports it, otherwise UPDATE-by-recreate gated on `aspects.confirm`.  Tag
attach is idempotent at the API level.

---

## Testing Strategy

- `MockVSphereClient` returns deterministic api-group method responses and
  fake `TaskHandle`s that `wait` returns immediately.
- Property tests: idempotent apply, inverse destroy, category+tag round-trip
  identity.
- Validate-table tests confirm object-bucket, NSX-less LB, interconnect, and
  unsupported shared-FS rejections.
- Library-item-vs-template fallback is tested for both branches.
- Datastore selection tested with capacity tables.
- Live runs gated by `RUN_LIVE_VSPHERE=1` against a homelab vCenter.
