# V8 Coding Agents

This directory provides a centralized location for files related to AI coding
agents (e.g. `gemini-cli`) used for development within the V8 source tree.

The goal is to provide a scalable and organized way to share prompts and tools
among developers, accommodating the various environments (Linux, Mac, Windows)
and agent types in use.

## Setup & Installation

This repository functions as a plugin. It provides Skills, Rules, and MCP Servers.

### 1. Installing the Plugin

To install this plugin symlink it into your plugins directory:
```bash
mkdir -p ~/.gemini/jetski/plugins
ln -s $(pwd) ~/.gemini/jetski/plugins/v8-agents
```

### 2. Installing MCP Servers

This plugin uses several MCP servers defined in `mcp_config.json`.

**v8-utils (v8-mcp)**
See extensions/v8-utils/README.md.

The rest use `vpython3` and are located inside the `extensions/` directory. They will run directly from the repository.

## Directory Structure

### Extensions & MCP Servers

V8-approved extensions & MCP servers. See [README.md](extensions/README.md).

### Skills

On-demand expertise for specific tasks. See [README.md](skills/README.md).

## Contributing

Please freely add self-contained task prompts and prompt templates.

New MCP server configurations should be for owned and supported MCP servers and
include OWNERS.
