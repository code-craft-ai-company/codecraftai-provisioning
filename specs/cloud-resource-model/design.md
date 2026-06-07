# Design

## Overview

The cloud resource model is the neutral Python type vocabulary that every venue
provisioner consumes and every spec author produces.  No model class talks to a cloud
SDK directly.  Each class is a `SchemaObject` (from `codecraftai-configuration`) with
typed `SchemaField` declarations, giving callers a single class that supports both
direct Python construction and `from_dict`/`to_dict` for YAML loaders and inventory
emit.

Construction-time validation is **shape-only** (types, enum membership, CIDR parseable,
port range monotonic).  Semantic validation that requires looking across resources —
subnet-in-network containment, sibling subnet non-overlap, accelerator support on the
chosen venue — runs in the lifecycle layer's `validate` stage (see
[cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md)).

This separation keeps model classes useful in isolation (tests, ad-hoc construction,
landscape emit) while keeping cross-resource invariants centralised in one place.

---

## Architecture

```
   YAML spec file                  Python caller
        │                                │
        ▼                                ▼
   schema loader                  CloudNetwork(...)
        │                                │
        └──── from_dict ────────────► SchemaObject base
                                         │
                                         ▼
                              shape-only validation
                                         │
                                         ▼
                              typed model instance
                                         │
                                         ▼
              ┌──────────────────────────┴──────────────────────────┐
              │                                                     │
              ▼                                                     ▼
   provisioner.validate(...)                          provisioner.plan/apply(...)
   cross-resource semantic checks                     venue-specific translation
```

---

## Data Model

Every class lives under
`source/packages/ccai/provisioning/model/cloud/` — one file per class, file name
all-lowercase, class name PascalCase, per the project's class-per-file standard.

```python
class CloudNetwork(SchemaObject):
    name: str
    cidr: str
    region: str
    tags: List[Dict[str, str]]

    @classmethod
    def from_dict(cls, *, payload: Dict[str, Any]) -> "CloudNetwork": ...
    def to_dict(self) -> Dict[str, Any]: ...


class CloudSubnet(SchemaObject):
    name: str
    network: str            # name reference to a CloudNetwork
    cidr: str
    zone: str
    public: bool
    tags: List[Dict[str, str]]


class CloudIngressRule(SchemaObject):
    protocol: str           # tcp|udp|icmp|all
    from_port: int
    to_port: int
    source_cidrs: List[str]
    source_sg: Optional[str]
    description: str


class CloudEgressRule(SchemaObject):
    protocol: str
    from_port: int
    to_port: int
    dest_cidrs: List[str]
    dest_sg: Optional[str]
    description: str


class CloudSecurityGroup(SchemaObject):
    name: str
    network: str
    ingress_rules: List[CloudIngressRule]
    egress_rules: List[CloudEgressRule]
    tags: List[Dict[str, str]]


class CloudKeyPair(SchemaObject):
    name: str
    public_key_material: str


class CloudImage(SchemaObject):
    family: str             # "ubuntu" | "debian" | "rhel" | "windows-server"
    version: str            # "24.04"
    architecture: str       # "x86_64" | "arm64"
    owner: Optional[str]


class CloudInstance(SchemaObject):
    name: str
    profile_ref: str
    image: CloudImage
    size: str          # neutral instance-size token (CloudInstanceSizeCatalog,
                       # e.g. "general.large") OR a venue-native size string.
    subnet: str
    security_groups: List[str]
    keypair: Optional[str]
    user_data_script: Optional[str]
    public_ip: bool
    tags: List[Dict[str, str]]
    vpn_join: Optional["VPNJoinSpec"]                       # see vpn-join-spec
    accelerators: Optional[List["CloudAcceleratorSpec"]]     # see accelerator-and-interconnect-model
    interconnect: Optional["CloudInterconnect"]
    placement_group: Optional[str]
    shared_fs_mounts: Optional[List["SharedFsMountSpec"]]
    preemption_policy: Literal["FAIL", "REACQUIRE", "BEST_EFFORT"] = "FAIL"


class CloudStorageVolume(SchemaObject):
    name: str
    size_gb: int
    type: str               # "ssd" | "hdd" | "nvme" | venue-mapped value
    attached_to: Optional[str]
    mount: Optional[str]
    tags: List[Dict[str, str]]


class CloudObjectBucket(SchemaObject):
    name: str
    region: str
    versioning: bool
    public: bool
    tags: List[Dict[str, str]]


class CloudLoadBalancer(SchemaObject):
    name: str
    scheme: Literal["internet-facing", "internal"]
    listeners: List[Dict[str, Any]]
    target_instance_names: List[str]
    tags: List[Dict[str, str]]


class CloudDnsRecord(SchemaObject):
    zone: str
    name: str
    record_type: Literal["A", "AAAA", "CNAME", "TXT", "MX", "SRV"]
    values: List[str]
    ttl_seconds: int


class CloudResourceProfile(SchemaObject):
    name: str
    kind: Literal["network","subnet","sg","instance","volume","bucket","dns","keypair","lb"]
    payload: Dict[str, Any]   # validated against the matching model class
```

---

## Module Layout

```
source/packages/ccai/provisioning/model/cloud/
├── cloudnetwork.py
├── cloudsubnet.py
├── cloudsecuritygroup.py
├── cloudingressrule.py
├── cloudegressrule.py
├── cloudkeypair.py
├── cloudimage.py
├── cloudinstance.py
├── cloudstoragevolume.py
├── cloudobjectbucket.py
├── cloudloadbalancer.py
├── clouddnsrecord.py
└── cloudresourceprofile.py    # gains typed kind discriminator
```

---

## CIDR Handling

All CIDR fields are parsed through `ipaddress.ip_network(strict=False)` at construction.
Sibling-subnet non-overlap and subnet-in-network containment are checked in the
lifecycle `validate` stage using `ipaddress.IPv4Network.overlaps()` /
`.subnet_of()`.  No venue-specific CIDR arithmetic lives in the model.

---

## See Also

- [accelerator-and-interconnect-model](../accelerator-and-interconnect-model/design.md) —
  optional fields on `CloudInstance`.
- [vpn-join-spec](../vpn-join-spec/design.md) — optional `vpn_join` field on `CloudInstance`.
- [cloud-provisioner-lifecycle](../cloud-provisioner-lifecycle/design.md) — consumer of
  the model; runs semantic validation.
- [preemption-policy](../preemption-policy/design.md) — `preemption_policy` field on
  `CloudInstance`.
- [cloud-provisioning-config-schema](../../../codecraftai-configuration/specs/cloud-provisioning-config-schema/design.md) —
  YAML loader that consumes `from_dict`.

---

## Testing Strategy

- **Unit tests** — construct each class with valid payloads; assert `to_dict/from_dict`
  round-trip identity.
- **Negative tests** — assert `SchemaValidationError` for: malformed CIDR, empty name,
  oversize name, inverted port range, missing source on a rule, unsupported record type.
- **Property tests (`hypothesis`) ⊙:**
  - `cidr_in_network_strategy()` generates `(network_cidr, subnet_cidr)` pairs where
    the subnet is guaranteed contained; the property asserts
    `IPv4Network(subnet).subnet_of(IPv4Network(network))`.
  - `sibling_subnets_strategy()` generates N non-overlapping subnets inside a parent
    network; the property asserts pairwise `not a.overlaps(b)`.
  - `ingress_egress_pair_strategy()` generates rule pairs and asserts
    `from_dict(to_dict(r)) == r`.
  - `profile_dispatch_strategy()` generates any-kind profile and asserts exactly one
    matching model class accepts the payload.
- All property tests run inside the same `unittest` harness as example tests.
