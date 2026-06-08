# RunPod Workload Provisioner

`RunpodWorkloadProvisioner` is a **`WorkloadProvisioner`** (PLAN §7.2) for the
RunPod GPU cloud. RunPod is **container-shaped**, not VM-shaped: the API
surface is Pods, Pod Templates, GPU Types, and Network Volumes. Every
`WorkloadJob` / `WorkloadService` becomes a RunPod **pod** (a container, not a
Kubernetes Pod) bound to a GPU type and a container image. Because the unit of
provisioning is a container, this is a `WorkloadProvisioner`, not a
`CloudProvisioner`.

## Honest fit — what RunPod lacks

RunPod has no VPC, subnet, security group, load balancer, or DNS API. The
provisioner is honest about this:

- `CloudObjectBucket` / `CloudLoadBalancer` / `CloudDnsRecord` —
  rejected at `validate` (`RpValidationError`).
- `CloudInterconnect` with a non-`NONE` kind — rejected at `validate`
  (RunPod offers no inter-pod IB fabric).
- `CloudNetwork` / `CloudSubnet` / `CloudSecurityGroup` / `CloudKeyPair` —
  not realised; `validate` emits a warning.
- `CloudSharedFilesystem(VENUE_NATIVE)` — realised as a RunPod Network
  Volume (attach by `existing_id`, or provisioned as a new volume).

## Auth flow

The provisioner drives `codecraftai-interop-runpod`'s `RunpodClient`, which
authenticates with a `RunpodApiKeyCredential` (Bearer token) against the
RunPod REST API at `rest.runpod.io/v1`.

## Lifecycle

`validate / plan / apply / destroy / inventory`:

- **validate** — resolves every accelerator to a RunPod GPU type, probes
  Secure Cloud capacity for the requested data center, and applies the
  honest-fit rejections / warnings above.
- **plan** — lists Pods and Network Volumes by the
  `<name>-<run-id-short>` prefix and emits `PlannedAction`s. A drifted GPU
  type yields UPDATE-by-recreate. A re-plan of an applied spec is all SKIP.
- **apply** — ensures Network Volumes, then launches a pod per workload.
  Idempotent: an all-SKIP plan makes no mutating call. A destructive plan
  (UPDATE / DELETE) is gated on `aspects.confirm`.
- **destroy** — stops and terminates the run's pods, de-registers VPN
  devices via `IVPNControlPlane.delete_device`, then deletes the run's
  Network Volumes.
- **inventory** — emits `ProvisionedResource` records for the run's Pods
  (public IP + overlay IP when known) and Volumes.

## VPN bring-up — userspace-mode Tailscale

RunPod containers run without `NET_ADMIN` and have no `/dev/net/tun` device,
so a `VPNJoinSpec` is realised as a **userspace-mode** Tailscale bring-up
(`tailscale up --tun=userspace-networking`) rendered by
`RpContainerStartRenderer` into the pod's container start command. There is no
cloud-init on a container; the bring-up logic is a deterministic shell script
handed to the pod as its `dockerArgs`.

## Tags

RunPod has no native pod tag field, so neutral tags are persisted in a sidecar
JSON file (`RpSidecarTag`) under `.output/provisioning/<runid>/runpod-tags.json`.
The inventory snapshot is written to
`.output/provisioning/<runid>/runpod-inventory.json`.

## See also

- [cloud-resource-model](../../../../../../specs/cloud-resource-model/design.md)
- [cloud-provisioner-lifecycle](../../../../../../specs/cloud-provisioner-lifecycle/design.md)
- [workload-venue-model](../../../../../../specs/workload-venue-model/design.md)
- [vpn-join-spec](../../../../../../specs/vpn-join-spec/design.md)
- `codecraftai-interop-runpod/AGENTS.md`
