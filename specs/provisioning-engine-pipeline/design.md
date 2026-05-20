# Design

## Overview

The provisioning engine pipeline is the venue-agnostic conductor that runs every
provisioning request.  It replaces the current `ProvisioningEngine` stub with an
ordered pipeline of named stages, each of which calls into one or more
`CloudProvisioner` / `WorkloadProvisioner` instances.

Stage order is fixed.  Within a stage, the engine drives resources in the order
yielded by a topological sort over the resource dependency graph computed from the
parsed spec.  The sort uses Kahn's algorithm with a deterministic tiebreaker
(alphabetical by resource name) so two runs over the same spec produce the same
order — the property tests pin this.

The engine itself owns no venue-specific knowledge.  Every venue-aware decision lives
in the provisioner subclasses; the engine only knows about kinds (`network`, `subnet`,
`sg`, ...) and the dependency edges between them.

---

## Architecture

```
   YAML spec ─► load_spec ─► PipelineSpec (typed)
                                    │
                                    ▼
                       build_dependency_graph
                                    │
                              topo_sort (stable)
                                    │
   ┌────────────────────────────────┴───────────────────────────────┐
   │                       Pipeline Stages                          │
   │                                                                │
   │  1. LOAD_VALIDATE          → provisioner.validate per venue    │
   │  2. PLAN                   → provisioner.plan    per venue     │
   │  3. APPLY_NETWORKING       → kinds: network, subnet, sg, keypair│
   │  4. APPLY_COMPUTE          → kinds: instance, volume, attach   │
   │  5. APPLY_DNS_STORAGE_LB   → kinds: dns, bucket, lb            │
   │  6. BOOTSTRAP_VPN          → IVPNControlPlane mint + verify    │
   │  7. VERIFY                 → wait for running + vpn registered │
   │  8. EMIT_LANDSCAPE_INVENTORY → landscape.yaml emit             │
   └────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                          run state persisted to
                          .output/provisioning/<runid>/
```

---

## Data Model

```python
class PipelineStage(Enum):
    LOAD_VALIDATE                 = "load_validate"
    PLAN                          = "plan"
    APPLY_NETWORKING              = "apply_networking"
    APPLY_COMPUTE                 = "apply_compute"
    APPLY_DNS_AND_STORAGE_AND_LB  = "apply_dns_and_storage_and_lb"
    BOOTSTRAP_VPN                 = "bootstrap_vpn"
    VERIFY                        = "verify"
    EMIT_LANDSCAPE_INVENTORY      = "emit_landscape_inventory"


class PipelineSpec(SchemaObject):
    apod: Dict[str, Any]
    environment: Dict[str, Any]
    venues: List[Union[CloudVenue, WorkloadVenue]]
    networks: List[CloudNetwork]
    subnets: List[CloudSubnet]
    security_groups: List[CloudSecurityGroup]
    keypairs: List[CloudKeyPair]
    instances: List[CloudInstance]
    volumes: List[CloudStorageVolume]
    buckets: List[CloudObjectBucket]
    load_balancers: List[CloudLoadBalancer]
    dns_records: List[CloudDnsRecord]
    shared_filesystems: List[CloudSharedFilesystem]
    workload_jobs: List[WorkloadJob]
    workload_clusters: List[WorkloadCluster]
    workload_services: List[WorkloadService]


class PipelinePlan(SchemaObject):
    per_venue_plans: Dict[str, ProvisioningPlan]
    topological_order: List[Tuple[str, str]]   # (kind, name)


class ProvisioningEngine:
    def __init__(self, *, spec: PipelineSpec, runid: str) -> None: ...

    @classmethod
    def from_spec_file(cls, *, path: str) -> "ProvisioningEngine": ...

    def validate(self, *, aspects: Aspects) -> None: ...
    def plan(self, *, aspects: Aspects) -> PipelinePlan: ...
    def apply(self, *, aspects: Aspects) -> Dict[str, ProvisioningResult]: ...
    def destroy(self, *, aspects: Aspects) -> None: ...
    def inventory(self, *, aspects: Aspects) -> Dict[str, List[ProvisionedResource]]: ...
```

---

## Dependency Graph

Edges (consumer → producer):

```
   subnet     → network
   sg         → network
   instance   → subnet
   instance   → sg
   instance   → keypair
   volume     → instance         (when attached_to is set)
   dns        → instance         (when values reference instance name/IP)
   lb         → instance         (target_instance_names)
   mount      → shared_filesystem
   instance   → vpn_join.credential
```

Kahn's algorithm produces a stable order with alphabetical tiebreaker on
`(kind, name)`.  Cycles raise `SchemaSemanticError` listing the cycle members.

---

## Stage Bodies

Each stage is a small method on `ProvisioningEngine`.  Sketches:

```python
def _stage_apply_networking(self, *, aspects: Aspects) -> None:
    networking_kinds = {"network", "subnet", "sg", "keypair"}
    for venue_name, provisioner in self._provisioners.items():
        ordered = [(k, n) for (k, n) in self._topo_order if k in networking_kinds]
        provisioner.apply_subset(kinds=ordered, aspects=aspects)
    return
```

`apply_subset` is a helper on the base provisioner that filters its full apply to a
restricted kind set, preserving topological order within the subset.

---

## Module Layout

```
source/packages/automojo/provisioning/
├── provisioningengine.py             # replaces today's stub
├── pipelinespec.py
├── pipelinestage.py
├── pipelineplan.py
├── dependencygraph.py
└── stages/
    ├── loadvalidate.py
    ├── planstage.py
    ├── applynetworkingstage.py
    ├── applycomputestage.py
    ├── applydnsstoragelbstage.py
    ├── bootstrapvpnstage.py
    ├── verifystage.py
    └── emitlandscapeinventorystage.py
```

---

## Run Identity and Persistence

Every pipeline run carries a `runid` (UUID4).  The engine creates
`.output/provisioning/<runid>/` and writes:

- `spec.yaml` — the input spec, normalised
- `plan.yaml` — `PipelinePlan`
- `result.yaml` — `Dict[venue_name, ProvisioningResult]`
- `inventory.yaml` — full inventory per venue
- `landscape.yaml` — emitted block consumable by `automojo-landscaping`
- `stages.log` — per-stage entry/exit/duration

Details on resumability and state persistence live in the
[provisioning-state-persistence](../provisioning-state-persistence/design.md) spec.

---

## See Also

- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md)
- [workload-venue-model](../workload-venue-model/design.md)
- [cloud-init-injection](../cloud-init-injection/design.md)
- [provisioning-state-persistence](../provisioning-state-persistence/design.md)
- [landscape-inventory-emit](../landscape-inventory-emit/design.md)
- [vpn-join-spec](../vpn-join-spec/design.md)

---

## Testing Strategy

- **Unit tests** — construct `PipelineSpec` from a small YAML; assert venue
  provisioners are instantiated; assert stage methods exist and are invoked in
  order by `apply`.
- **Stage isolation tests** — each stage method is called against a Fake provisioner
  and verified to touch only its declared kinds.
- **Property tests (`hypothesis`) ⊙:**
  - **Subnet-before-instance:** for any valid spec, every instance's apply call
    happens after its subnet's apply call (verified via call-order recording on
    the Fake).
  - **DNS-after-instance:** every DNS record that references an instance is
    applied after that instance.
  - **Sort stability:** sorting the same dependency graph twice yields the same
    order.
  - **Cycle detection:** synthesised spec with deliberate cycle raises
    `SchemaSemanticError` (and nothing else).
- **Destroy-reverse test:** assert destroy calls happen in reverse topological
  order across all stages.
