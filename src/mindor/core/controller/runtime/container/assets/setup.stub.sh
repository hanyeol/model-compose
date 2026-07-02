#!/bin/sh
# Injected in place of the user's setup.sh when the project has none.
# Provides a no-op so the derived Dockerfile can COPY unconditionally.
exit 0
