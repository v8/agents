# ECMA-262 Specification Research MCP Server

This MCP server provides tools for researching the ECMAScript specification (ECMA-262) and active TC39 proposals.

## Tools

### Specification Research & Navigation
*   `ecma262_get_operation`: Get algorithm for an abstract operation by name. Steps that can invoke JavaScript user code (getters, setters, Proxy traps, `Symbol.toPrimitive`, etc.) are annotated with `⚡`.
*   `ecma262_get_evaluation`: Get evaluation algorithm for a grammar production.
*   `ecma262_section`: Get rendered Markdown content of a specific section/clause.
*   `ecma262_sections`: Get rendered content of multiple sections.
*   `ecma262_search`: Search the specification index.
*   `ecma262_signature`: Get signature of an abstract operation.
*   `ecma262_lookup`: Resolve ancestry hierarchy of a section.
*   `ecma262_callers`: Find all algorithm steps across the specification that call or reference a given operation.
*   `ecma262_parse`: Parse JavaScript code to AST using `@babel/parser`.

### TC39 Proposal Support
*   `ecma262_load_proposal`: Securely fetch and index a TC39 proposal from the official `tc39` / `ecma` namespace (e.g. `explicit-resource-management`, `temporal`, `defer-import-eval`, `decorators`).
*   `ecma262_list_proposals`: List all loaded proposals and show the active specification context.
*   `ecma262_use_proposal`: Switch active context between Base ECMA-262 and a loaded proposal.
*   `ecma262_diff`: Diff an abstract operation or clause between Base ECMA-262 and a proposal with `<ins>` and `<del>` markers.

## Annotations
*   **`⚡` (Can Call User Code)**: Steps tagged with `<emu-meta effects="user-code">` in the spec (e.g. object property access, method calls, Proxy traps) are annotated with `⚡` to assist with reentrancy, invariant validation, and JIT side-effect analysis.

## Setup

The server relies on data generated from the ECMAScript specification. It will attempt to download and process the spec on first run if not already present in `~/.local/share/ecma262-mcp`.
