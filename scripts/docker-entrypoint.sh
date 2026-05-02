#!/bin/bash

set -e

# Docker deployments should run the worker process directly by default.  The
# optional web console can still be enabled explicitly with EK_ENABLE_WEB=1, and
# the web console starts the worker immediately on container startup unless
# --wait is passed. Setting EK_WEBPASS alone only configures the console password
# and must not switch the container into web mode implicitly.
if [ "${EK_ENABLE_WEB:-0}" = "1" ]; then
    exec "embykeeperweb" "--basedir" "/app" "--public" "$@"
else
    exec "embykeeper" "--basedir" "/app" "$@"
fi
