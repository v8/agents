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
git clone https://github.com/v8/agents.git third_party/agents
mkdir -p .agents/plugins
ln -s $(pwd)/third_party/agents .agents/plugins/v8-agents
```

### 2. Installing MCP Servers

To install the MCP servers, you need to manually add them to your global configuration file at `~/.gemini/jetski/mcp_config.json`.

Please refer to the `mcp_config.json` file in the root of this plugin directory for the server definitions to copy. You will need to replace `${extensionPath}` with the actual **absolute** path to this plugin directory when copying to the global configuration.

## Directory Structure

### Extensions & MCP Servers

V8-approved extensions & MCP servers. See [README.md](extensions/README.md).

### Skills

On-demand expertise for specific tasks. See [README.md](skills/README.md).

## Contributing

Please freely add self-contained task prompts and prompt templates.

New MCP server configurations should be for owned and supported MCP servers and
include OWNERS.
