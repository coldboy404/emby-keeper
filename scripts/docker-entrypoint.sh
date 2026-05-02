#!/bin/bash

set -e

# Docker self-host deployments should run the CLI worker directly.  Passing
# --instant makes each container start/restart execute one run immediately, and
# because --once is not set the normal configured schedules stay active after
# that first run.
exec "embykeeper" "--basedir" "/app" "--instant" "$@"
