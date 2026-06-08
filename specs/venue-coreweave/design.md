# Design — CoreWeave Workload Provisioner

## Overview

`CoreweaveWorkloadProvisioner` is a **`WorkloadProvisioner`** (PLAN §7.2),
not a `CloudProvisioner`.  The unit of provisioning is a Kubernetes workload
graph (Deployments / StatefulSets / Jobs / Services / Ingresses / PVCs), not
a VM.  The provisioner composes two interop clients:

1. `codecraftai-interop-coreweave` — minimal client that authenticates with a
   `CoreweaveApiCredential`, mints a kubeconfig (TTL-managed), enumerates
   node pools, and exposes CoreWeave-specific machine type metadata.
2. `codecraftai-interop-kubernetes` — the official K8s Python client wrapped in
   the ccai Aspects pattern (IMPLEMENTATION-PLAN §1.17).  All actual
   resource calls go here.

PLAN §7.6 commits CoreWeave to the "mint kubeconfig, chain to K8s" auth flow.
The CoreWeave client never makes resource calls — only the K8s client does.

A separate sibling, `CoreweaveCloudProvisioner` (a regular `CloudProvisioner`
for raw-VM workloads), is out of scope for this spec; see PLAN §7.3.

See Also:
- [cloud-resource-model](../cloud-resource-model/design.md)
- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md)
- [workload-venue-model](../workload-venue-model/design.md)
- [vpn-join-spec](../vpn-join-spec/design.md)
- `codecraftai-interop-coreweave/Agents.md`
- `codecraftai-interop-kubernetes/specs/kubernetes-client/design.md`

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    ProvisioningEngine                        │
└──────────────────────────┬───────────────────────────────────┘
                           │ workload spec
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              CoreweaveWorkloadProvisioner                    │
│  provisioning/venues/coreweave/coreweaveworkloadprov...py    │
└────┬──────────────────┬─────────────────┬──────────────────┘
     │                  │                 │
     ▼                  ▼                 ▼
┌────────────┐ ┌────────────────┐  ┌──────────────────────────┐
│CwNodePool  │ │CwLabelTrans    │  │CwManifestRenderer        │
│selector    │ │ neutral↔labels │  │ Deployment/Job/Sunk Slurm│
└────────────┘ └────────────────┘  └──────────────────────────┘
     │                                       │
     ▼                                       ▼
┌──────────────────────────┐    ┌──────────────────────────────┐
│ CoreweaveClient          │    │ KubernetesClient             │
│ codecraftai-interop-coreweave│   │ codecraftai-interop-kubernetes  │
│  mint_kubeconfig         │    │  apply_manifest / get / ...  │
└──────────────────────────┘    └──────────────────────────────┘
```

Call paths used by `apply`:

- CoreWeave: `mint_kubeconfig(ttl=aspects.kubeconfig_ttl)` once per run.
- K8s interop, per resource: `get_namespace` / `create_namespace`,
  `apply_manifest(yaml_dict, aspects)` for ServiceAccount / Secret / PVC /
  Deployment / StatefulSet / Service / Ingress.
- For Sunk Slurm-on-K8s: render the upstream Sunk manifests (Slurm
  controller, slurmd DaemonSet, MySQL StatefulSet) and apply via the same
  interop.

---

## Mapping Table

| Neutral model | CoreWeave / K8s primitive | Notes |
| --- | --- | --- |
| `WorkloadVenue` | kubeconfig context | minted by the CoreWeave client. |
| `WorkloadCluster.node_pools` | per-pool `nodeSelector`/affinity | resolver per `CwNodePoolSelector`. |
| `WorkloadJob` | K8s Job | `restart_policy` honoured. |
| `WorkloadService` | K8s Deployment + Service (+ Ingress when public). |
| `CloudAcceleratorSpec(GPU)` | container `resources.limits["nvidia.com/gpu"]` + node selector. |
| `CloudInterconnect(INFINIBAND_*)` | IB-fabric affinity label + RDMA device plugin requests. |
| `CloudSharedFilesystem(VAST/WEKA, existing_id)` | PVC bound to existing CSI volume. |
| `CloudImage` | container `image` field | family/version → image URL via resolver. |
| `VPNJoinSpec` | sidecar `tailscale` container in Pod, OR subnet-router DaemonSet. |
| Tags | K8s labels (sanitised) | round-trip identity for conformant inputs. |
| `sub_mode="sunk"` | Sunk Slurm-on-K8s manifest bundle. |

---

## Module Layout

```
source/packages/ccai/provisioning/venues/coreweave/
├── __init__.py
├── coreweaveworkloadprovisioner.py
├── cwnodepoolselector.py        # accelerator → node pool selector
├── cwlabeltranslator.py
├── cwmanifestrenderer.py        # Deployment/Job/Service/Ingress YAML
├── cwsunkrenderer.py            # Sunk Slurm-on-K8s manifest bundle
├── cwvpnsidecar.py              # tailscale sidecar / subnet router renderer
├── cwplanbuilder.py
├── cwapplystages.py
├── cwdestroystages.py
├── cwinventory.py
└── cwerrors.py
```

---

## Idempotency

The K8s interop's `apply_manifest` is server-side apply (or
`create-or-replace`) and is idempotent at the API level.  Re-applying an
unchanged manifest is a SKIP.  The provisioner adds the `codecraftai-run-id`
label to every resource and queries by it during plan/inventory.  Kubeconfig
freshness is re-checked at each call and re-minted if expired.

---

## Testing Strategy

- `MockKubernetesClient` returns deterministic resource records keyed on
  `(kind, namespace, name)`.
- `MockCoreweaveClient` returns a deterministic kubeconfig + node-pool
  catalog.
- Property tests: idempotent apply, inverse destroy, label round-trip
  identity for conformant inputs.
- Sunk Slurm branch tested separately — manifest bundle determinism by
  content hash.
- VPN sidecar vs. subnet-router rendering is table-driven.
- Live runs gated by `RUN_LIVE_COREWEAVE=1` (incurs GPU charges).
