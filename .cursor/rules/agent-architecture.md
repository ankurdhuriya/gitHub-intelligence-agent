---
description: Rules for building and debugging the GitHub Intelligence Agent
globs: *.py
---

# Engineering Directives for GitHub Intelligence Agent

You are an expert AI Engineer specializing in the Model Context Protocol (MCP) and Gemini 3 Flash execution loops. 

## Architectural Stack
- **Language:** Python 3.11+ (Asyncio)
- **Frameworks:** `google-generativeai`, `mcp` python SDK
- **Core Design:** Client-Server architecture via JSON-RPC/stdio endpoints.

## Tool Calling & Constraints
- **Gemini strictness:** Gemini 3 Flash expects precise FunctionDeclaration schemas. 
- **Dynamic Translation:** When parsing the GitHub MCP server schemas, recursively strip out unsupported JSON-Schema keywords (like `$ref` or `additionalProperties`) before sending declarations to Gemini.
- Always handle multi-turn execution dynamically by capturing `function_calls` and returning `function_response` parts cleanly. Do not wrap tool outputs in standard user text blocks.

## Code Style
- Use descriptive type hinting for all async definitions.
- Implement robust exception handling for network/JSON-RPC timeouts when interacting with the GitHub MCP server.
