# Design — Equinix Metal Provisioner

## Overview

`EquinixMetalCloudProvisioner` realises the neutral resource model on Equinix
Metal, a bare-metal venue.  The unit of provisioning is a **Device** (a physical
server), not a VM, which has implications: provisioning latency is measured in
minutes, not seconds; not every Metal plan is available in every metro; and
in-place "resize" is not a concept.  The provisioner is honest about this in
the plan output and the destroy gating.

API calls go through `codecraftai-interop-equinix-metal`'s `MetalClient`, which
wraps the `packet-python` SDK against `api.equinix.com/metal/v1/`.

See Also:
- [cloud-resource-model](../cloud-resource-model/design.md)
- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md)
- [vpn-join-spec](../vpn-join-spec/design.md)
- `codecraftai-interop-equinix-metal/Agents.md`

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    ProvisioningEngine                        │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              EquinixMetalCloudProvisioner                    │
│  provisioning/venues/equinix/equinixmetalcloudprov...py      │
└────┬──────────────────┬───────────────────┬─────────────────┘
     │                  │                   │
     ▼                  ▼                   ▼
┌─────────────┐  ┌────────────────┐  ┌──────────────────────┐
│MetalResolver│  │MetalTagTrans   │  │MetalUserDataRenderer │
│plan/img/met │  │ k=v string list│  │ userdata + vpn_join  │
└─────────────┘  └────────────────┘  └──────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│        MetalClient (codecraftai-interop-equinix-metal)          │
│   projects / vlans / ip-reservations / ssh-keys / devices    │
│   packet-python SDK against api.equinix.com/metal/v1         │
└──────────────────────────────────────────────────────────────┘
```

REST call paths used by `apply`:

- `GET /projects/{id}/virtual-networks` / `POST` (VLANs)
- `GET /projects/{id}/ips` / `POST /projects/{id}/ips` (IP reservations)
- `GET /projects/{id}/ssh-keys` / `POST`
- `GET /projects/{id}/devices` / `POST` with `userdata`
- `POST /devices/{id}/actions` (reboot, reinstall)

---

## Mapping Table

| Neutral model | Equinix Metal resource | Notes |
| --- | --- | --- |
| `apod` envelope | Project | configured per run; not created by the provisioner. |
| `CloudNetwork` | (no first-class VPC) | folded into project; per-VLAN scoping. |
| `CloudSubnet` | VLAN + IP Reservation | layer-2; IPs reserved separately. |
| `CloudSecurityGroup` | (no native) | recorded in tags; honest warning at validate. |
| `CloudKeyPair` | Project SSH Key | dedup by fingerprint. |
| `CloudImage` | OS slug | `ubuntu/24.04` → `ubuntu_24_04`. |
| `CloudInstance` | Device | `size` → plan slug (`c3.medium.x86`, `n3.xlarge.x86`, `g3.large.x86`). |
| `CloudInstance.accelerators` | GPU device plan | minimal catalog. |
| `CloudInterconnect` | unsupported | `validate`-error for non-`NONE`. |
| `CloudStorageVolume` | (separate product, attach-existing only in v1) | else `validate`-error. |
| `CloudObjectBucket` | unsupported | `validate`-error. |
| `CloudLoadBalancer` | unsupported in v1 | `validate`-error. |
| `CloudDnsRecord` | external (out of scope) | warn today. |
| `CloudSharedFilesystem` | unsupported | `validate`-error. |
| `VPNJoinSpec` | `userdata` cloud-init | identical to other venues. |
| Tags | string list `["k=v", ...]` | round-trip identity. |

---

## Module Layout

```
source/packages/ccai/provisioning/venues/equinix/
├── __init__.py
├── equinixmetalcloudprovisioner.py
├── metalresolver.py
├── metaltagtranslator.py
├── metaluserdatarenderer.py
├── metalplanbuilder.py
├── metalapplystages.py
├── metaldestroystages.py
├── metalinventory.py
└── metalerrors.py
```

---

## Idempotency

Reads use project-scoped listings filtered by tag.  Device plan changes are
UPDATE-by-recreate (Metal does not resize); reinstall is a separate action and
is not used by the provisioner.

---

## Testing Strategy

- `MockMetalClient` returns deterministic paged JSON.
- Property tests: idempotent apply, inverse destroy, tag round-trip identity.
- Validate-table tests confirm object-storage, interconnect, shared-FS, and LB
  rejections.
- Live runs gated by `RUN_LIVE_METAL=1` (long-running — Device provisioning is
  measured in minutes).
