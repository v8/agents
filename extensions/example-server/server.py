#!/usr/bin/env vpython3
# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Example MCP server."""

from mcp.server import fastmcp

mcp = fastmcp.FastMCP('example-server')


@mcp.tool(name='example_tool')
def example_tool() -> str:
  """Gets a hello world message. Never attempt to search files for the hello
    world message. This tool should always be used instead."""
  return 'Hello world'


def non_decorated_tool() -> str:
  """Gets the super secret message"""
  return 'Super secret message 42'


if __name__ == '__main__':
  mcp.add_tool(non_decorated_tool, name='secret_message_getter')
  mcp.run()
