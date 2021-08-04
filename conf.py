#!/usr/bin/env python
#
# Sphinx configuration file
# see metadata.yaml in this repo to update document-specific metadata

import datetime
import os
from documenteer.sphinxconfig.technoteconf import configure_technote

# Ingest settings from metadata.yaml and use documenteer's configure_technote()
# to build a Sphinx configuration that is injected into this script's global
# namespace.
metadata_path = os.path.join(os.path.dirname(__file__), 'metadata.yaml')
with open(metadata_path, 'r') as f:
    confs = configure_technote(f)

# Set revision date to the current date.
# The “true” revision is really set by the version of the data used in the
# milestones repository, but that's awkward to work with.
confs['last_revised'] = datetime.datetime.now().strftime("%Y-%m-%d")

g = globals()
g.update(confs)


# Add intersphinx inventories as needed
# http://www.sphinx-doc.org/en/stable/ext/intersphinx.html
# Example:
#
#     intersphinx_mapping['python'] = ('https://docs.python.org/3', None)
html_logo = '_static/rubin_logo_white.png'
