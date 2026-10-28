.. _02-00-getting-started:

***************
Getting Started
***************

Installation
============

The cloud venues install with the package:

.. code-block:: bash

    pip install codecraftai-provisioning

The coreweave, hyperv, libvirt and xcpng venues drive their hosts through the
``codecraftai-interop-*`` driver packages, which ship in the ``hypervisors`` extra:

.. code-block:: bash

    pip install "codecraftai-provisioning[hypervisors]"

Importing one of those venues without the extra raises ``ConfigurationError``, and the
message names the extra to install.
