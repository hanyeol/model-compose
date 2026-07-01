#!/bin/sh
# Controller container entrypoint.
#
# When the launcher mounts a workspace bundle at /mnt/bootstrap (model-compose.yml
# and webui dirs), copy it into /workspace before exec'ing the real command.
# The bundle is rebuilt per launch and mounted read-only so the container can
# treat /workspace as writable scratch space without affecting the host.
set -e

if [ -d /mnt/bootstrap ]; then
    cp -a /mnt/bootstrap/. /workspace/
fi

exec "$@"
