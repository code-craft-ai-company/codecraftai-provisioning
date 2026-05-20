# Requirements

## Introduction

After a successful `apply`, the provisioning engine emits a
`landscape.yaml`-compatible block listing every provisioned host with a full
`DeviceAddressSet` (public, private, overlay).  The block is consumable directly by
`automojo-landscaping`, so a user can run `arcli provision apply` then immediately use
the emitted landscape file to drive tests against the new infrastructure.

This spec defines the emit format, the source-of-truth mapping from
`ProvisionedResource` records to landscape device entries, and the contract that
downstream landscaping packages rely on.

---

## Requirements

### Requirement 1: Emit Trigger

**User Story:** As a framework user, I want a landscape block produced automatically.

#### Acceptance Criteria

1. WHEN the engine's `EMIT_LANDSCAPE_INVENTORY` stage runs THE SYSTEM SHALL write
   `landscape.yaml` to the run's persistence directory.
2. WHEN the `apply` aborted before VERIFY THE SYSTEM SHALL still emit a partial
   landscape covering whatever hosts reached `running`.
3. WHEN no instances were provisioned THE SYSTEM SHALL emit a valid (empty)
   landscape document, not omit the file.

---

### Requirement 2: Landscape Schema Compatibility

**User Story:** As an `automojo-landscaping` user, I want the emitted file to load
directly into the landscape loader without translation.

#### Acceptance Criteria

1. THE SYSTEM SHALL produce a YAML document with the top-level keys `apod`,
   `environment`, `pod`, `devices` matching the existing
   `automojo-landscaping/specs/landscape-yaml-schema` schema.
2. THE SYSTEM SHALL include a `vpn:` top-level block when any provisioned instance
   has a `vpn_join` spec, listing the providers and credential vault references.
3. WHEN the emitted file is parsed by `automojo-landscaping` THE SYSTEM SHALL pass
   landscaping's own schema validation with no warnings.

---

### Requirement 3: DeviceAddressSet per Host

**User Story:** As a landscaping consumer, I want every host listed with all known
addresses, not a single `_host` string.

#### Acceptance Criteria

1. WHEN emitting a device entry THE SYSTEM SHALL include an `addresses` mapping with
   the keys `public`, `private`, and (when applicable) `overlay`.
2. WHEN an instance has `public_ip=False` THE SYSTEM SHALL omit the `public` key
   (not emit it as null).
3. WHEN an instance has `vpn_join` and the overlay address is known THE SYSTEM SHALL
   emit `overlay: { provider: <name>, address: <ip>, magic_dns: <fqdn> }`.
4. THE SYSTEM SHALL never emit the legacy single-string `_host` field.

---

### Requirement 4: Source Mapping

**User Story:** As a framework author, I want a clear rule for which inventory
record produces which landscape entry.

#### Acceptance Criteria

1. THE SYSTEM SHALL emit one device entry per `ProvisionedResource` with
   `kind == "instance"` from any venue's inventory.
2. THE SYSTEM SHALL pull `public` and `private` addresses from the inventory
   record's `attributes`.
3. WHEN the instance has `vpn_join` THE SYSTEM SHALL query the VPN control plane
   for the overlay address and MagicDNS / Twingate FQDN.
4. WHEN the overlay query fails THE SYSTEM SHALL still emit the public/private
   entry and log a warning.

---

### Requirement 5: Tags and Groups

**User Story:** As a landscaping author, I want the emitted devices grouped the same
way the spec grouped them.

#### Acceptance Criteria

1. THE SYSTEM SHALL preserve every `tag` from the provisioned resource on the
   emitted device entry.
2. WHEN the spec organised instances into groups THE SYSTEM SHALL emit matching
   `group` membership on each device entry.
3. THE SYSTEM SHALL emit the `venue` name on each device so downstream coordinators
   know which provisioner to talk to.
