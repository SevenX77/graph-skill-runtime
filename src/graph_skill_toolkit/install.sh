#!/bin/sh
set -eu
bundle_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
unset NODE_OPTIONS NODE_PATH
if [ ! -f "$bundle_dir/runtimes/node/bin/node" ]; then
  echo 'Extract the complete Graph Skill archive for this operating system and architecture.' >&2
  exit 1
fi
chmod u+x "$bundle_dir/runtimes/node/bin/node" "$bundle_dir/runtimes/python/bin/python3"
exec "$bundle_dir/runtimes/node/bin/node" "$bundle_dir/bin/graph-skill.mjs" install "$@"
