# Design — RunPod Workload Provisioner

## Overview

`RunpodWorkloadProvisioner` is a **`WorkloadProvisioner`** per PLAN §7.2.
RunPod is container-shaped — the API surface is Pods, Templates, GPU Types,
and Network Volumes — so this provisioner does not consume the
`CloudNetwork`/`CloudSubnet`/`CloudSecurityGroup` parts of the neutral
model.  Calls go through `codecraftai-interop-runpod`'s `RunpodClient` against
the GraphQL endpoint at `https://api.runpod.io/graphql`.

VPN bring-up is constrained: RunPod containers run with limited
capabilities, so Tailscale must run in **userspace mode**
(`tailscale up --tun=userspace-networking`), and overlay routing into the
container is via the `tailscale serve`/`tailscale proxy` userspace SOCKS
listener.  The cloud-init renderer accounts for this.

Tags are not natively supported by the RunPod API; the provisioner uses a
sidecar JSON file like `venue-lambdalabs` does.

See Also:
- [cloud-resource-model](../cloud-resource-model/design.md)
- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md)
- [workload-venue-model](../workload-venue-model/design.md)
- [vpn-join-spec](../vpn-join-spec/design.md)
- `codecraftai-interop-runpod/Agents.md`

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    ProvisioningEngine                        │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              RunpodWorkloadProvisioner                       │
│  provisioning/venues/runpod/runpodworkloadprovisioner.py     │
└────┬──────────────────┬─────────────────┬──────────────────┘
     │                  │                 │
     ▼                  ▼                 ▼
┌────────────┐ ┌────────────────┐  ┌──────────────────────────┐
│RpResolver  │ │RpSidecarTag    │  │RpContainerStartRenderer  │
│gpu/template│ │ JSON sidecar   │  │ dockerArgs + userspace TS│
└────────────┘ └────────────────┘  └──────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│        RunpodClient (codecraftai-interop-runpod)                │
│   pods / volumes / templates / gpu-types                     │
│   GraphQL against api.runpod.io/graphql                      │
└──────────────────────────────────────────────────────────────┘
```

GraphQL operations used by `apply`:

- `query gpuTypes(...)` for capacity probe.
- `query networkVolumes(...)` / `mutation createNetworkVolume(...)`
- `query pods(...)` / `mutation podFindAndDeployOnDemand(...)` or
  `mutation podRentInterruptable(...)` (Community Cloud)
- `mutation podStop(...)` / `mutation podTerminate(...)`

---

## Mapping Table

| Neutral model | RunPod primitive | Notes |
| --- | --- | --- |
| `WorkloadVenue` | API endpoint + tier | configured per run. |
| `WorkloadJob` / `WorkloadService` | Pod | image + entrypoint + env. |
| `CloudAcceleratorSpec(GPU)` | `gpuTypeId` + `gpuCount` | resolver maps neutral name → RunPod gpuType. |
| `CloudInterconnect` | unsupported | `validate`-error. |
| `CloudImage` | container `imageName` | family/version → image URL. |
| `CloudSharedFilesystem(VENUE_NATIVE, existing_id)` | Network Volume attach | by id. |
| `CloudNetwork`/`CloudSubnet`/`CloudSecurityGroup`/`CloudKeyPair` | not realised | warn at validate. |
| `CloudObjectBucket`/`CloudLoadBalancer`/`CloudDnsRecord` | unsupported | `validate`-error. |
| `VPNJoinSpec` | `containerStartScript` adds `tailscale up --tun=userspace-networking`. |
| Tags | sidecar JSON file under `.output/provisioning/<runid>/`. |

---

## Module Layout

```
source/packages/ccai/provisioning/venues/runpod/
├── __init__.py
├── runpodworkloadprovisioner.py
├── rpresolver.py
├── rpsidecartag.py
├── rpcontainerstartrenderer.py     # userspace-tailscale-aware
├── rpplanbuilder.py
├── rpapplystages.py
├── rpdestroystages.py
├── rpinventory.py
└── rperrors.py
```

---

## Idempotency

Reads list Pods by name prefix `<spec-name>-<run-id-short>`.  Pods matching
the desired GPU type + template + start script are SKIP candidates.  Any
substantive change is UPDATE-by-recreate gated on `aspects.confirm`.
Network Volumes are reused when name + size match.

---

## Testing Strategy

- `MockRunpodClient` returns deterministic GraphQL responses.
- Property tests: idempotent apply, inverse destroy, sidecar-tag round-trip
  identity.
- Userspace-Tailscale start-script content-hash determinism is asserted.
- Secure vs Community tier branch is table-driven.
- Live runs gated by `RUN_LIVE_RUNPOD=1`.
