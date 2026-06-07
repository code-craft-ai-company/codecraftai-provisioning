# CoreWeave Workload Provisioner

`CoreweaveWorkloadProvisioner` is a **`WorkloadProvisioner`** (PLAN §7.2) for
the CoreWeave Kubernetes Service (CKS) venue. The unit of provisioning is a
Kubernetes workload graph — Jobs, Deployments, StatefulSets, Services, PVCs —
not a virtual machine. CoreWeave is Kubernetes-native, so this is a
`WorkloadProvisioner`, not a `CloudProvisioner`.

## Auth flow — mint kubeconfig, then drive Kubernetes

Per PLAN §7.6 the venue follows the "mint kubeconfig, chain to Kubernetes"
auth flow. Two interop clients are composed:

1. `codecraftai-interop-coreweave` — `CoreweaveClient` authenticates with a
   `CoreweaveApiCredential`, mints a TTL-managed kubeconfig, and enumerates
   CoreWeave node pools / accelerator metadata. It never speaks the
   Kubernetes API.
2. `codecraftai-interop-kubernetes` — `KubernetesClient` is built from the
   kubeconfig dict the CoreWeave client mints. Every actual resource call
   routes through its workload primitives.

The provisioner's `_ensure_kubernetes_client` mints the kubeconfig once per
run and constructs the `KubernetesClient` from `kubeconfig.as_dict()`.

## Lifecycle

`validate / plan / apply / destroy / inventory` operate over `WorkloadJob`,
`WorkloadService`, and `WorkloadCluster`:

| Neutral model | Kubernetes primitive |
| --- | --- |
| `WorkloadJob` | Kubernetes Job |
| `WorkloadService` | Deployment + Service |
| `CloudAcceleratorSpec(GPU)` | `nodeSelector` + `resources.limits["nvidia.com/gpu"]` |
| `CloudInterconnect(INFINIBAND_*)` | IB-fabric affinity label + `nvidia.com/hostdev` |
| `SharedFsMountSpec` (VAST / WEKA) | PVC bound to a CoreWeave CSI StorageClass |
| `VPNJoinSpec` | userspace-mode Tailscale sidecar, or subnet-router DaemonSet |
| neutral tags | Kubernetes labels (sanitised, round-trip identity) |
| `sub_mode="sunk"` | Sunk Slurm-on-Kubernetes manifest bundle |

`validate` rejects `SLURM`/`RAY`/`NOMAD` venue kinds unless
`sub_mode="sunk"`. Idempotency comes from the Kubernetes interop's
read-before-create `apply`; re-planning an applied spec yields only SKIPs.
`inventory` persists a snapshot under
`.output/provisioning/<runid>/coreweave-inventory.json`.

## See also

- [cloud-resource-model](../../../../../../specs/cloud-resource-model/design.md)
- [cloud-provisioner-lifecycle](../../../../../../specs/cloud-provisioner-lifecycle/design.md)
- [workload-venue-model](../../../../../../specs/workload-venue-model/design.md)
- [vpn-join-spec](../../../../../../specs/vpn-join-spec/design.md)
- `codecraftai-interop-coreweave` — the CoreWeave control-plane client
- `codecraftai-interop-kubernetes` — the Kubernetes interop client
