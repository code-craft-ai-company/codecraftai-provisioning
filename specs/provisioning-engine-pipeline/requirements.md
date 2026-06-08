# Requirements

## Introduction

The provisioning engine pipeline replaces today's `ProvisioningEngine` shell with a
staged pipeline that drives the five-verb lifecycle (`validate / plan / apply /
destroy / inventory`) across a mixed set of `CloudProvisioner` and
`WorkloadProvisioner` instances in a venue-agnostic way.

The pipeline runs eight stages in fixed order:

1. Load & validate spec
2. Plan per venue
3. Apply networking
4. Apply compute
5. Apply DNS / object storage / load balancers
6. Bootstrap VPN
7. Verify
8. Emit landscape inventory

Stage order respects the resource dependency graph: networks before subnets, subnets
before instances, instances before DNS records that point at them, etc.  The pipeline
performs a topological sort over the parsed spec to determine intra-stage ordering
and rejects spec graphs that contain cycles.

This spec covers the pipeline's structural behaviour and the algebraic invariants of
its topological sort.

---

## Requirements

### Requirement 1: Eight-Stage Pipeline

**User Story:** As a framework user, I want every provisioning run to follow the
same stage order regardless of venue.

#### Acceptance Criteria

1. THE SYSTEM SHALL execute exactly these stages in this order:
   `LOAD_VALIDATE`, `PLAN`, `APPLY_NETWORKING`, `APPLY_COMPUTE`,
   `APPLY_DNS_AND_STORAGE_AND_LB`, `BOOTSTRAP_VPN`, `VERIFY`,
   `EMIT_LANDSCAPE_INVENTORY`.
2. WHEN any stage raises THE SYSTEM SHALL halt subsequent stages and surface the
   exception unwrapped (no swallowing per Python standards).
3. THE SYSTEM SHALL log entry/exit and duration for each stage.

---

### Requirement 2: Spec Loading

**User Story:** As a framework user, I want the YAML spec parsed into typed objects.

#### Acceptance Criteria

1. WHEN `load_spec(path)` runs THE SYSTEM SHALL read the YAML file and construct
   typed model objects via each class's `from_dict`.
2. WHEN the YAML is malformed THE SYSTEM SHALL raise `ConfigurationError`.
3. WHEN any model `from_dict` raises THE SYSTEM SHALL bubble the
   `SchemaValidationError` unchanged.

---

### Requirement 3: Per-Venue Plan

**User Story:** As a framework user, I want the engine to compute a per-venue plan.

#### Acceptance Criteria

1. WHEN the PLAN stage runs THE SYSTEM SHALL call `provisioner.plan(aspects=...)` on
   every venue's provisioner.
2. THE SYSTEM SHALL aggregate per-venue plans into a `PipelinePlan` record carrying
   `{venue_name: ProvisioningPlan}`.
3. WHEN `aspects.dry_run` is `True` THE SYSTEM SHALL return the `PipelinePlan` and
   skip all `APPLY_*`, `BOOTSTRAP_VPN`, `VERIFY`, and `EMIT_LANDSCAPE_INVENTORY`
   stages.

---

### Requirement 4: Apply Networking → Compute → DNS/Storage/LB

**User Story:** As a framework user, I want resources applied in the dependency
order that lets later resources reference earlier ones.

#### Acceptance Criteria

1. WHEN `APPLY_NETWORKING` runs THE SYSTEM SHALL apply only `network`, `subnet`,
   `sg`, `keypair` kinds per venue.
2. WHEN `APPLY_COMPUTE` runs THE SYSTEM SHALL apply `instance`, `volume`, and
   volume-attachment kinds per venue.
3. WHEN `APPLY_DNS_AND_STORAGE_AND_LB` runs THE SYSTEM SHALL apply `dns`, `bucket`,
   `lb` kinds per venue.
4. WHEN intra-stage ordering matters (subnet ⇨ instance dependency, etc.) THE
   SYSTEM SHALL execute resources in dependency-graph topological-sort order.
5. WHEN the dependency graph contains a cycle THE SYSTEM SHALL raise
   `SchemaSemanticError` listing the cycle members.

---

### Requirement 5: Bootstrap VPN

**User Story:** As a provisioning author, I want every instance with a `vpn_join`
spec to actually join the mesh.

#### Acceptance Criteria

1. WHEN `BOOTSTRAP_VPN` runs THE SYSTEM SHALL collect every instance with
   `vpn_join is not None` from the apply results.
2. WHEN the VPN credential is `TailscaleOAuthCredential` THE SYSTEM SHALL mint a
   per-instance ephemeral auth key via `IVPNControlPlane.mint_authkey` with TTL ≤
   15 minutes.
3. THE SYSTEM SHALL invoke
   `cloud_init_injection.render_for_instance(...)` and rely on the venue
   provisioner having injected the rendered payload at create time; for instances
   that were `SKIP`ped, the SYSTEM SHALL NOT re-inject.

---

### Requirement 6: Verify

**User Story:** As a framework user, I want each instance verified before the engine
declares success.

#### Acceptance Criteria

1. WHEN `VERIFY` runs THE SYSTEM SHALL poll each created instance for `running`
   state using `codecraftai-waiting` with aspects-controlled interval and timeout.
2. WHEN an instance has `vpn_join` set THE SYSTEM SHALL additionally poll
   `IVPNControlPlane.list_devices` until the instance appears.
3. WHEN any instance fails to reach the expected state inside the aspect-controlled
   timeout THE SYSTEM SHALL raise `ProvisioningVerifyError` listing the offending
   instance(s).

---

### Requirement 7: Emit Landscape Inventory

**User Story:** As a downstream `codecraftai-landscaping` user, I want a usable
`landscape.yaml`-compatible block at the end of every successful run.

#### Acceptance Criteria

1. WHEN `EMIT_LANDSCAPE_INVENTORY` runs THE SYSTEM SHALL delegate to the
   `landscape-inventory-emit` module to produce a `landscape.yaml` fragment under
   the run's persistence directory.

---

### Requirement 8: Destroy Path

**User Story:** As a framework user, I want destroy to reverse the same stages.

#### Acceptance Criteria

1. WHEN `destroy(aspects)` runs THE SYSTEM SHALL invoke `provisioner.destroy` on
   every venue in reverse stage order and reverse topological-sort order within a
   stage.
2. WHEN `aspects.confirm` is `False` THE SYSTEM SHALL refuse to run and raise
   `SemanticError`.

---

### Requirement 9: Property-Test Invariants ⊙

**User Story:** As a maintainer, I want stage ordering and topological sort behaviour
proven by property tests.

#### Acceptance Criteria

1. THE SYSTEM SHALL include property tests asserting:
   - For any randomly-generated valid spec, every `instance` is applied **after**
     its `subnet` dependencies.
   - For any spec, every `dns` resource is applied **after** the instance whose
     IP it references.
   - The topological sort is **stable** — repeated sorts of the same graph
     produce the same order.
   - Any spec graph containing a cycle raises `SchemaSemanticError` (and not any
     other exception type).
