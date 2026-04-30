#!/bin/bash

set -e

# Docker deployments should run the worker process directly by default.  The
# optional web console can still be enabled explicitly with EK_ENABLE_WEB=1, but
# setting EK_WEBPASS alone must not switch the container into the web wrapper: in
# that mode the worker waits for a browser/socket event and a Docker restart can
# leave the service idle until someone opens the page and confirms startup.
if [ "${EK_ENABLE_WEB:-0}" = "1" ]; then
    exec "embykeeperweb" "--basedir" "/app" "--public" "$@"
else
    exec "embykeeper" "--basedir" "/app" "$@"
fi
