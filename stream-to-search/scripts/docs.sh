#!/usr/bin/env bash
# The instaclustr_sdk API reference, generated from the docstrings by pdoc.
#
# Usage:  scripts/docs.sh                # serve it at http://localhost:8080
#         scripts/docs.sh -o docs/api    # or write static HTML to docs/api/ (gitignored)
# Other arguments go to pdoc as well (see pdoc --help).
#
# Needs `pip install -e ".[ai,docs]"`. Override the interpreter with PYTHON (default python3).
set -euo pipefail

python="${PYTHON:-python3}"
"$python" -c 'import pdoc, instaclustr_sdk.agent' 2>/dev/null || {
  echo "$python can't import pdoc and instaclustr_sdk.agent; run: pip install -e \".[ai,docs]\" (or set PYTHON)" >&2
  exit 1
}

# agent and rag are named explicitly because pdoc follows the package's __all__, which leaves
# them out so that `import instaclustr_sdk` doesn't need the AI extras. Without the [ai] extra,
# pdoc would only warn and skip agent, hence the check above. -d google renders the "Args:"
# sections in the agent's tool docstrings.
exec "$python" -m pdoc -d google instaclustr_sdk instaclustr_sdk.agent instaclustr_sdk.rag "$@"
