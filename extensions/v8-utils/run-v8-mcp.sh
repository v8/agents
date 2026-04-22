#!/bin/bash

# Ensure we can find v8-mcp
if command -v v8-mcp >/dev/null 2>&1; then
  exec v8-mcp "$@"
else
  echo "v8-mcp not found. Please install it." >&2
  exit 1
fi
