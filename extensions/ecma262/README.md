# ECMA-262 Specification Research MCP Server

This MCP server provides tools for researching the ECMAScript specification (ECMA-262).

## Tools

*   `ecma262_search`: Search the specification index.
*   `ecma262_section`: Get content of a specific section.
*   `ecma262_sections`: Get content of multiple sections.
*   `ecma262_lookup`: Resolve ancestry of a section.
*   `ecma262_signature`: Get signature of an abstract operation.
*   `ecma262_get_operation`: Get algorithm for an operation.
*   `ecma262_get_evaluation`: Get evaluation algorithm for a grammar production.
*   `ecma262_parse`: Parse JavaScript code to AST using @babel/parser.

## Setup

The server relies on data generated from the ECMAScript specification. It will attempt to download and process the spec on first run if not already present in `~/.local/share/ecma262-mcp`.
