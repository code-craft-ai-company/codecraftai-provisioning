============================
Code Craft AI Provisioning
============================

The ``codecraftai-provisioning`` package provides the cloud-provisioning layer for the ccai suite. It defines a vendor-neutral model for declaring cloud resources and a set of venue-specific provisioner implementations that can realise those resources on the three major public clouds.

Highlights
==========

- Vendor-neutral ``CloudResourceProfile``, ``CloudDevice``, ``CloudGroup``, ``CloudVenue``, and abstract ``CloudProvisioner`` under ``provisioning/model/cloud/``.
- Concrete provisioners under ``provisioning/venues/``: ``AwsCloudProvisioner``, ``AzureCloudProvisioner``, and ``GoogleCloudProvisioner``.
- Top-level ``ProvisioningEngine`` that drives a provisioning run end-to-end.
- Integrates with ``codecraftai-landscaping`` so cloud-provisioned hosts can be folded into a landscape once they exist.
- Cloud authentication via ``codecraftai-credentials``.

Repository Structure
====================

- ``development/`` - Runtime environment scripts.
- ``repository-setup/`` - Repository homing and setup scripts.
- ``source/packages/`` - Package source code.
- ``source/testroots/testbase/`` - TestBase test roots.
- ``userguide/`` - Standards, conventions, and documentation.

Environment Setup
=================

When working in a Codex container:

.. code-block:: bash

   ./development/setup-agent-container

For local development:

.. code-block:: bash

   ./repository-setup/rehome-repository
   ./development/setup-envrionment

Running Tests
=============

Activate the virtual environment:

.. code-block:: bash

   source .venv/bin/activate

Run TestBase tests (when test roots are populated):

.. code-block:: bash

   testbase testing run --root source/testroots/testbase --includes=ccai --output=./.output

Standards and Conventions
=========================

- Naming conventions: ``userguide/10-02-naming-conventions.rst``
- Code organization: ``userguide/10-01-code-organization.rst``
- Coding standards: ``userguide/10-00-coding-standards.rst``

Additional Resources
====================

- User guide entry point: ``userguide/userguide.rst``
