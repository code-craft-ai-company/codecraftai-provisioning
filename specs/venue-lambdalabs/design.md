# Design — Lambda Labs Provisioner

## Overview

`LambdalabsCloudProvisioner` realises the neutral resource model on the Lambda
Labs Cloud through `automojo-interop-lambdalabs`, which wraps the Lambda Cloud
REST API on `RestClientBase`.  Lambda's API surface is the smallest of any
public venue in this plan: Instances, SSH Keys, File Systems, and 1-Click
Clusters.  No VPC.  No firewall.  No object storage.  No DNS.  The provisioner
is honest about every gap.

Because Lambda has no native tag/label system, the provisioner uses a sidecar
JSON file under `.output/provisioning/<runid>/` to record the neutral tag list,
keyed by Instance ID.  Plan and inventory consult both Lambda's API and the
sidecar.

See Also:
- [cloud-resource-model](../cloud-resource-model/design.md)
- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md)
- [vpn-join-spec](../vpn-join-spec/design.md)
- `automojo-interop-lambdalabs/Agents.md`

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    ProvisioningEngine                        │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              LambdalabsCloudProvisioner                      │
│  provisioning/venues/lambdalabs/lambdalabscloudprov...py     │
└────┬───────────────────┬────────────────────┬───────────────┘
     │                   │                    │
     ▼                   ▼                    ▼
┌─────────────┐  ┌──────────────────┐  ┌──────────────────────┐
│LlResolver   │  │LlSidecarTag      │  │LlUserDataRenderer    │
│type/region  │  │  JSON sidecar    │  │ user_data + vpn_join │
└─────────────┘  └──────────────────┘  └──────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│        LambdalabsClient (automojo-interop-lambdalabs)        │
│   instances / ssh-keys / file-systems / 1-click-clusters     │
│   RestClientBase against cloud.lambda.ai/api/v1              │
└──────────────────────────────────────────────────────────────┘
```

REST call paths used by `apply`:

- `GET /instance-types` (capacity check)
- `GET /ssh-keys` / `POST /ssh-keys`
- `GET /file-systems`
- `GET /instances` / `POST /instance-operations/launch`
- `POST /instance-operations/terminate`
- 1-Click Cluster endpoints (where exposed) for multi-node SKUs.

---

## Mapping Table

| Neutral model | Lambda primitive | Notes |
| --- | --- | --- |
| `CloudNetwork` / `CloudSubnet` / `CloudSecurityGroup` | not realised | warn at validate. |
| `CloudKeyPair` | SSH Key | dedup by name+key. |
| `CloudImage` | (no API; Lambda picks per instance-type) | unused. |
| `CloudInstance` | Instance | `size`/`accelerators` → `instance_type` slug. |
| `CloudAcceleratorSpec(H100×8)` | `gpu_8x_h100_sxm5` etc. | from resolver catalog. |
| `CloudInterconnect(INFINIBAND_NDR)` | 1-Click Cluster | when offered for the SKU. |
| `CloudStorageVolume` | not realised in v1 | warn at validate. |
| `CloudObjectBucket` / `CloudLoadBalancer` / `CloudDnsRecord` | unsupported | `validate`-error. |
| `CloudSharedFilesystem(VENUE_NATIVE, existing_id)` | File System attach | attach-only. |
| `VPNJoinSpec` | `user_data` in launch payload | identical pattern. |
| Tags | sidecar JSON file under `.output/provisioning/<runid>/`. |

---

## Module Layout

```
source/packages/automojo/provisioning/venues/lambdalabs/
├── __init__.py
├── lambdalabscloudprovisioner.py
├── llresolver.py
├── llsidecartag.py
├── lluserdatarenderer.py
├── llplanbuilder.py
├── llapplystages.py
├── lldestroystages.py
├── llinventory.py
└── llerrors.py
```

---

## Idempotency

Reads list instances and match by the `name` field encoding the spec name +
run-id-short prefix.  Re-applying a launched instance is a SKIP.
instance_type changes are UPDATE-by-recreate gated on `aspects.confirm`.

---

## Testing Strategy

- `MockLambdalabsClient` returns deterministic paged JSON.
- Property tests: idempotent apply, inverse destroy, sidecar-tag round-trip
  identity.
- Validate-table tests confirm rejections for object-storage, LB, DNS.
- 1-Click Cluster branch tested separately from single-Instance branch.
- Live runs gated by `RUN_LIVE_LAMBDA=1`.
