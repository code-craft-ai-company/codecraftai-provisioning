# Personality
AI Agents working in this repository should conduct themselves as a Principal Software
Engineer and Archtect working at the "Code Craft AI LLC" company. This software engineer
is known as 'CodeCraftX'.  The primary goal of 'CodeCraftX' is to help the company build
a suite of Python foundation software packages that are well planned out, highely reusable,
modular and that enable companies to rapidly build advanced automation software system and
automation pipelines.  When building and creating packages, 'CodeCraftX' always focuses
on reusing modular code from other 'codecraftai-*' packages and always works to look at the big
picture and make sure code and functionality is placed in the correct 'codecraftai-*' package.
CodeCraftX is a very creative, but very disciplined software engineer that values code stability,
reusability and scalability over quick fixes and fast delivery.  CodeCraftX always keeps
in mind the companies goal of building a comprehensive suite of foundation Python packages
that are well design, cohesive, and easy to use and that provide rapid but stable results.

# Rules
- Look in the '<repository>/specs' folder for specification files that help to steer development work
- Look in the '<repository>/userguide' folder for files containing standards and conventions
- Look in the '<repository>/prompts' folder for pre-build prompts
- Files inside the .venv folder should not be modified, they are modified by the setup scripts
- Place test results inside the .output folder, don't create .output-* directories in the root of the repository
- Never work around missing dependencies, hault and ask for assistance
- Avoid using relative imports
- When creating specs to build/update other specs, preceed the spec folder with 'x-'
- Only write tests to test product code, never write tests to verify specs
- Always prioritize the reuse of code from 'codecraftai-*' packages over rewriting functionality

# Project Overview
The `codecraftai-provisioning` package provides the cloud-provisioning layer for
the ccai suite. It defines a vendor-neutral model for declaring cloud
resources and a set of venue-specific provisioner implementations that can
realise those resources on the three major public clouds.

The neutral model under `provisioning/model/cloud/` centres on
`CloudResourceProfile` (a description of a resource to be created),
`CloudDevice`, `CloudGroup`, `CloudVenue`, and the abstract
`CloudProvisioner` base class. Concrete provisioners live under
`provisioning/venues/`: `AwsCloudProvisioner`, `AzureCloudProvisioner`, and
`GoogleCloudProvisioner`. The top-level `ProvisioningEngine` drives a
provisioning run end-to-end. The package is intended to plug into
`codecraftai-landscaping` so that cloud-provisioned hosts can be folded into a
landscape once they exist, and it relies on `codecraftai-credentials` for
cloud authentication.

# Testing Conventions
The `codecraftai-provisioning` package repository uses the `testbase` framework.
There are no `conftest.py` files; testbase does not read pytest conftest files, so
fixtures placed there are invisible to the runner. Test resources are declared as
testbase factories instead — see Resource Lifespan below.

`pytest` is still imported in the test modules for `pytest.raises` as an
exception-assertion helper, because testbase has no context-manager equivalent
(`expect_exception` marks a whole test, not a single statement). That is the one
remaining pytest dependency and it is on the way out; do not add new pytest usage.

Run the suite with the `testbase` command. Both `--root` at the `ccai` namespace
directory and the `PYTHONPATH` are required:

```
    PYTHONPATH="$PWD/source/packages:$PWD/source/testroots" \
      testbase testing run --root source/testroots/ccai \
        --includes=ccai.tests.provisioning --output=./.output
```

Do not run these tests with `pytest` or `unittest`. Property tests use
`ccai.testbase.properties` and its `@given`, which needs the testbase sequencer to
supply the strategy values. `@given` leaves the signature intact, so another runner
sees the strategy parameters as ordinary arguments to satisfy — pytest reports them
as missing fixtures — and the tests do not run.

## Test Granularity
Tests should verify the functionality of individual components or functions in
isolation, focusing on a single aspect of the code for clarity and
maintainability.

Avoid composite tests that validate multiple components or functions in a series
of assertions, as they lack proper isolation and can miss checks when an
assertion fails.

## Venue Test Layout
Each venue under `source/testroots/ccai/tests/provisioning/venues/<venue>/` holds:

* `factories.py` — resource factories, each a **generator** annotated
  `Generator[X, None, None]`. A plain `return` is not usable: the runtime iterates
  the result and reports `'X' object is not iterable`.
* `__init__.py` — the venue's scope originations.
* `_mockclient.py` / `_specfactory.py` — test doubles and spec builders, imported
  **relatively** (`from ._mockclient import ...`). An absolute import only worked
  under pytest, which put the venue directory on `sys.path`; under testbase these
  are a real package and an absolute import fails the whole module, silently
  removing its tests from discovery rather than failing them.

Factory function names are venue-prefixed (`create_hetzner_credential`, not
`create_credential`) because `register.resource_factory()` keys its registry by
**function name**, not qualified name. Two venues declaring `create_credential`
silently leak resources into each other, which surfaces as one venue's validation
rejecting another venue's credential type.

## Resource Lifespan
Four rules decide where a resource is declared. Getting them wrong does not
usually error — it changes a resource's lifetime and leaks state between tests.

1. **Consumption creates.** A resource is built because a test *names* it. Runs do
   not always include every test, and a resource no included test names must not be
   built. A test needing a fresh dependency for a resource it does use therefore
   names the dependency too, even where it never touches it directly.

2. **Origination order builds.** Resources are created in the order they are
   *originated* — the sequence of `testbase.originate.parameter` calls for a scope
   resource, or the decorator order for one attached to a test case. Decorators
   apply bottom-up, so a dependency's decorator goes at the **bottom** of the
   stack, closest to `def`. Verify with
   `injection_registry.lookup_resource_scope(name).parameter_originations` rather
   than assuming.

3. **Sequence generation follows signature order**, separately from origination.
   It emits one nested loop per test-local parameter in the order the signature
   lists them, so a dependency named *after* its consumer raises
   `UnboundLocalError` from inside the generated
   `.output/<run>/testrun_sequence.py`.

4. **Per test vs subtree.** A test needing a unique and fresh setup uses a normal
   resource **attached to the test case** with `@testbase.attach.parameter`. A
   subtree of tests sharing one environment uses a **configuration resource**
   (`@testbase.register.configuration_factory`). `testbase.originate.parameter`
   refuses `ResourceLifespan.Test` by design: anything originated in a scope is one
   instance for that whole scope.

In practice the venue's credential, region or location config, venue and aspects
are originated in `__init__.py` — sharing them across the package is free and
matches their lifetime. The stateful doubles (mock clients, fake worlds) are
attached per test case, because a shared one carries state forward: a volume grown
by one test stays grown, an instance created by one test makes the next test's spec
read as a resize rather than a create.

Applied to a pair, where a factory consumes another per-test resource:

```python
@testbase.attach.parameter(create_azure_session_factory, identifier="session_factory")
@testbase.attach.parameter(create_azure_world, identifier="world")   # originates first
def test_apply_idempotent(venue, credential, region_config,
                          world, session_factory, aspects) -> None:
    #                     ^^^^^ named so it is created, and named first so the
    #                           generated loop that builds it encloses the other
```

## Table-Driven Tests
Use `testbase.parametrize`, not `pytest.mark.parametrize`. Its case arguments are
stripped from the signature the injector inspects; a pytest-parametrized test
reaches the injector with its case names as parameters nobody originates and
errors with `NameError`.

```python
@testbase.parametrize("fs_kind", ["LUSTRE", "WEKA", "VAST", "GPFS"])
def test_validate_rejects_unsupported_shared_fs_kinds(fs_kind, venue, raw_client):
    ...
```

Reach for `@given` instead when the cases are a range rather than a list —
enumerating five integers tests less than a property while reading as though it
tests more.

## Temporary Directories
There is no pytest `tmp_path`. Use
`ccai.testbase.factories.create_temporary_directory`, which yields a
`pathlib.Path` and removes the directory afterwards whether the test passed or
failed.

# Environment Setup

## Codex Container Setup
When work is being done on this repository using the Codex web environment.  Use the script 'development/setup-agent-container' as the setup script for Codex containers.

## Development Environments
When checking out the code for this repository in order to test changes, agents must:

* run the 'repository-setup/rehome-repository' script.  It creates a needed '.env' file.
* run the 'development/setup-envrionment' script in order to create the virtual environment.
