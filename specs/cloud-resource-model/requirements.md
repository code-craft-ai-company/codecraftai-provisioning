# Requirements

## Introduction

The cloud resource model defines the **neutral**, venue-independent Python classes that
describe every primitive piece of cloud infrastructure `automojo-provisioning` knows how
to stand up: networks, subnets, security groups and their rules, key pairs, images,
instances, storage volumes, object buckets, load balancers, and DNS records.  These
classes are the shared vocabulary that every venue provisioner (AWS, Azure, GCP,
DigitalOcean, Hetzner, Linode, Oracle, Equinix Metal, Vultr, vSphere, Proxmox, libvirt,
etc.) translates into venue-native API calls.

A spec file written against this model is portable: switching venues only changes the
`CloudVenue` reference, not the resource shapes.  The model is the foundation that
makes the four-verb lifecycle (`validate / plan / apply / destroy / inventory`) verb-
agnostic and venue-agnostic.

`CloudResourceProfile` gains a typed `kind` discriminator
(`Literal["network","subnet","sg","instance","volume","bucket","dns","keypair","lb"]`),
replacing today's free-form parameters dict, so callers and validators have a single
authoritative dispatch point per resource kind.

Every model object is a `SchemaObject` with typed fields and a `from_dict` constructor
so the same class is used by Python callers and by YAML loaders.  Construction validates
shape; semantic validation (e.g. subnet CIDR containment) lives in the lifecycle layer.

---

## Requirements

### Requirement 1: CloudNetwork

**User Story:** As a provisioning author, I want a venue-neutral `CloudNetwork`
abstraction so that a VPC (AWS), VNet (Azure), VPC (GCP), or Network (Hetzner) is
described with the same fields.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose `CloudNetwork(name: str, cidr: str, region: str,
   tags: List[Dict[str, str]])` as a `SchemaObject`.
2. WHEN `cidr` is not a valid IPv4 or IPv6 CIDR THEN THE SYSTEM SHALL raise
   `SchemaValidationError` at construction time.
3. WHEN `name` is empty or longer than the venue-neutral max (63 characters) THEN
   THE SYSTEM SHALL raise `SchemaValidationError`.
4. THE SYSTEM SHALL provide `from_dict(payload: Dict[str, Any]) -> CloudNetwork` that
   round-trips with `to_dict()`.

---

### Requirement 2: CloudSubnet

**User Story:** As a provisioning author, I want subnets that belong to a network with
a CIDR that lives **inside** the network's CIDR.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose `CloudSubnet(name, network: str, cidr, zone,
   public: bool, tags)`.
2. WHEN a `CloudSubnet.cidr` is not contained in its referenced `CloudNetwork.cidr`
   THEN THE SYSTEM SHALL raise `SchemaSemanticError` during lifecycle `validate`.
3. WHEN two sibling subnets in the same network overlap THEN THE SYSTEM SHALL raise
   `SchemaSemanticError`.
4. WHERE `public=True` THE SYSTEM SHALL signal venue provisioners to attach an
   internet gateway / external route / equivalent egress path.

---

### Requirement 3: CloudSecurityGroup, CloudIngressRule, CloudEgressRule

**User Story:** As a provisioning author, I want to describe ingress/egress rules in a
form every venue can translate.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose `CloudSecurityGroup(name, network, ingress_rules: List,
   egress_rules: List, tags)`.
2. THE SYSTEM SHALL expose `CloudIngressRule(protocol, from_port: int, to_port: int,
   source_cidrs: List[str], source_sg: Optional[str], description: str)`.
3. THE SYSTEM SHALL expose `CloudEgressRule` with identical fields except `dest_cidrs`
   replaces `source_cidrs` and `dest_sg` replaces `source_sg`.
4. WHEN `from_port > to_port` THEN THE SYSTEM SHALL raise `SchemaValidationError`.
5. WHEN both `source_cidrs` is empty and `source_sg` is `None` (or its egress
   equivalent) THEN THE SYSTEM SHALL raise `SchemaValidationError`.
6. WHEN any CIDR is malformed THEN THE SYSTEM SHALL raise `SchemaValidationError`.

---

### Requirement 4: CloudKeyPair, CloudImage

**User Story:** As a provisioning author, I want a single neutral way to describe SSH
key material and a desired image, regardless of venue.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose `CloudKeyPair(name, public_key_material: str)`.
2. WHEN `public_key_material` is empty THEN THE SYSTEM SHALL raise
   `SchemaValidationError`.
3. THE SYSTEM SHALL expose `CloudImage(family, version, architecture, owner)`.
4. WHERE a venue resolver receives a `CloudImage` THE SYSTEM SHALL produce a
   venue-specific identifier (AMI id, GCP image family resource, Azure SKU triple).

---

### Requirement 5: CloudInstance

**User Story:** As a provisioning author, I want a single instance shape that carries
everything a venue needs, including optional VPN join and accelerator slots.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose `CloudInstance(name, profile_ref, image, size, subnet,
   security_groups, keypair, user_data_script, public_ip: bool, tags, vpn_join,
   accelerators, interconnect, placement_group, shared_fs_mounts, preemption_policy)`.
2. WHEN `vpn_join` is set and its `provider == "twingate"` and the instance is NOT
   declared a connector host THEN THE SYSTEM SHALL raise `SchemaSemanticError`.
3. WHEN `accelerators` is set but the resolved venue does not support the requested
   model THEN THE SYSTEM SHALL raise `SchemaSemanticError` during `validate`.

---

### Requirement 6: CloudStorageVolume, CloudObjectBucket

**User Story:** As a provisioning author, I want neutral block and object storage
descriptors.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose `CloudStorageVolume(name, size_gb: int, type, attached_to,
   mount, tags)`.
2. WHEN `size_gb <= 0` THEN THE SYSTEM SHALL raise `SchemaValidationError`.
3. THE SYSTEM SHALL expose `CloudObjectBucket(name, region, versioning: bool,
   public: bool, tags)`.
4. WHERE the resolved venue does not support object buckets (e.g. raw vSphere) THE
   SYSTEM SHALL produce a clear validate-time error.

---

### Requirement 7: CloudLoadBalancer, CloudDnsRecord

**User Story:** As a provisioning author, I want to declare load balancers and DNS
records portably.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose `CloudLoadBalancer(name, scheme, listeners: List,
   target_instance_names: List[str], tags)`.
2. THE SYSTEM SHALL expose `CloudDnsRecord(zone, name, record_type, values: List[str],
   ttl_seconds: int)`.
3. WHEN `record_type` is not in the supported set
   (`A`, `AAAA`, `CNAME`, `TXT`, `MX`, `SRV`) THEN THE SYSTEM SHALL raise
   `SchemaValidationError`.

---

### Requirement 8: CloudResourceProfile Typed Kind Discriminator

**User Story:** As a framework author, I want a single typed dispatch on resource kind.

#### Acceptance Criteria

1. THE SYSTEM SHALL define `CloudResourceProfile.kind` as
   `Literal["network","subnet","sg","instance","volume","bucket","dns","keypair","lb"]`.
2. WHEN `kind` is not in the supported literal set THEN THE SYSTEM SHALL raise
   `SchemaValidationError`.
3. THE SYSTEM SHALL validate the per-kind payload against the matching model class
   above before returning a constructed profile.

---

### Requirement 9: Property-Test Invariants

**User Story:** As a maintainer, I want the model's algebraic invariants enforced
by property tests so refactors can't break them silently.

#### Acceptance Criteria

1. THE SYSTEM SHALL ship `hypothesis` strategies for every resource model class.
2. THE SYSTEM SHALL include property tests asserting:
   - CIDR containment: `subnet ⊂ network` always holds for valid pairs.
   - CIDR non-overlap: any two sibling subnets in one network never overlap.
   - Rule symmetry: an `(ingress, egress)` rule pair generated by the strategy
     round-trips through `to_dict / from_dict`.
   - Profile dispatch: every constructible profile resolves to exactly one model class.
