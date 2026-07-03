---
description: Constraints for managing the multi-turn agent execution loop and MCP integration
globs: "*.py"
---

# Engineering Directives: GitHub Intelligence Agent

You are an expert AI Engineer specializing in the Model Context Protocol (MCP) and Gemini 3 Flash tool orchestration. Maintain strict runtime constraints.

## 🧱 Architectural Stack
- **Language/Runtime:** Python 3.11+ (Asyncio)
- **Frameworks:** `google-generativeai`, `mcp` SDK
- **Core Design:** Client-Server architecture interacting with the official GitHub MCP server via JSON-RPC/stdio.

## 🛠️ Tool-Calling & Constraint Handling
- **Dynamic Schema Translation:** The official GitHub MCP server uses strict JSON schemas. Before converting these to Gemini's `FunctionDeclaration` objects, recursively sanitize and strip unsupported fields (e.g., `$ref`, `additionalProperties`) to prevent API validation errors.
- **Symmetric History Management:** When the model calls a tool, ensure the runtime catches `function_calls` and appends a corresponding `Part.from_function_response` block back into the history context. Do not wrap tool results in standard markdown or user roles, as this breaks Gemini's state machine and triggers infinite loops.

## 💻 Code Patterns
- Use explicit type-hinting for all asynchronous I/O loops.
- Implement isolated exception layers for JSON-RPC message passing to handle upstream network spikes gracefully.
