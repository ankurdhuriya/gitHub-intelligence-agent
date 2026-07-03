# AI Collaboration & Engineering Log: GitHub Intelligence Agent

This document outlines how I collaborated with **Cursor AI (using Gemini/Claude backends)** during the design, implementation, and debugging phases of the GitHub Intelligence Agent. 

It highlights architectural decisions, prompt iteration strategies, and real-time debugging loops where human oversight guided the AI to resolve complex edge cases involving the **Model Context Protocol (MCP)** and **Gemini 3 Flash**.

---

## 📂 Phase 1: Architecture Blueprint & Setup
**Objective:** Establish a robust agentic loop connecting Gemini 3 Flash with the official GitHub MCP server.

### 👤 Human (Ankur)
> "I want to build a Python-based GitHub Intelligence Agent that can run deep analysis, search, and research tasks over GitHub repositories using natural language. I plan to use Gemini 3 Flash as the primary LLM engine. I want to interface with GitHub using the official GitHub MCP (Model Context Protocol) server. How should I structure the core agentic loop so that Gemini dynamically discovers and executes tools provided by the MCP server?"

### 🤖 Cursor AI
> To connect Gemini 3 Flash with a Model Context Protocol (MCP) server, we need an intermediary orchestration layer that converts MCP tool schemas into Google's Function Calling format, handles tool execution requests from the model, executes them via the MCP server, and feeds the results back into the context.
>
> Here is the recommended directory structure to isolate the MCP client, the LLM agent loop, and the application layer:
>
> ```text
> ├── config.py           # API keys, MCP server paths, environment setup
> ├── mcp_client.py       # Manages connection to GitHub MCP server via JSON-RPC/stdio
> ├── agent.py            # Main Gemini 3 Flash routing, system prompts, tool translation
> ├── tools_bridge.py     # Map Gemini function signatures <=> MCP tool schemas
> └── main.py             # CLI interface / entry point
> ```
>
> Let's start by implementing `mcp_client.py` to handle the asynchronous sub-process lifecycle for the GitHub MCP server...

---

## 🔄 Phase 2: Iterative Refinement & Tool Translation
**Objective:** Translating dynamic JSON-RPC payloads between Gemini’s Function Declaration API and the MCP Specification.

### 👤 Human (Ankur)
> "The structural blueprint looks solid. Let's build out `tools_bridge.py`. The GitHub MCP server exposes complex JSON schemas for tools like `search_code` or `get_issue`. Gemini 3 Flash expects a strict `google.generativeai.types.FunctionDeclaration` object. Write a dynamic mapping utility that hooks into the initialized MCP client, fetches available tools dynamically, and constructs the tool definition dictionary for Gemini."

### 🤖 Cursor AI
> Here is a dynamic translator class. It connects to the running MCP lifecycle, queries `list_tools`, parses the JSON-Schema parameters, and map types (like `string`, `integer`, `array`) directly to `google.ai.generativelanguage.Type` fields:
>
> ```python
> # tools_bridge.py excerpt
> import google.generativeai as genai
> 
> class MCPToolBridge:
>     def __init__(self, mcp_client):
>         self.client = mcp_client
>         self.mcp_to_gemini_cache = {}
> 
>     async def generate_gemini_tools(self):
>         mcp_tools = await self.client.list_tools()
>         gemini_tools = []
>         
>         for tool in mcp_tools.tools:
>             # Save mapping for back-routing during execution
>             self.mcp_to_gemini_cache[tool.name] = tool
>             
>             # Translate JSON schema properties to Gemini parameters
>             properties = self._parse_schema_properties(tool.inputSchema)
>             
>             decl = genai.types.FunctionDeclaration(
>                 name=tool.name,
>                 description=tool.description,
>                 parameters=properties
>             )
>             gemini_tools.append(decl)
>             
>         return genai.types.Tool(function_declarations=gemini_tools)
> ```

### 👤 Human (Ankur) (Refinement)
> "Wait, there's an issue with nested arrays or complex reference objects (`$ref`) inside the GitHub MCP schema for operations like creating commits or deep issue filtering. Gemini 3 Flash’s function calling parser throws a validation error if the properties contain nested `$ref` objects or unsupported schema keys. Let’s refactor `_parse_schema_properties` to recursively sanitize the schema, stripping out or flattening anything that doesn't comply with Gemini's supported primitives."

### 🤖 Cursor AI
> Good catch. The official GitHub MCP server uses strict JSON-Schema drafts that include validation keywords (like `additionalProperties` or structural references) that break Gemini's tool constraints. Let's modify the code to flatten complex schemas and sanitize inputs recursively:
>
> ```python
> def _sanitize_property(self, schema_node):
>     # Recursively remove unsupported Gemini fields like $ref or additionalProperties
>     if isinstance(schema_node, dict):
>         sanitized = {}
>         for k, v in schema_node.items():
>             if k in ['type', 'description', 'properties', 'required', 'items']:
>                 sanitized[k] = self._sanitize_property(v)
>         return sanitized
>     return schema_node
> ```

---

## 🛠️ Phase 3: Debugging Loops & Resolving Hallucinations
**Objective:** Fixing multi-turn agent loops where Gemini gets stuck calling tools.

### 👤 Human (Ankur)
> "When evaluating complex prompts like *'Find all PRs mentioning a specific security flaw and summarize their review comments'*, Gemini gets into an infinite loop. It calls `search_pull_requests`, gets the list, but instead of calling `get_pull_request_review_comments` for individual items, it repeatedly calls the search tool with slight parameter variations. How can we fix this tool-execution hallucination or thrashing loop?"

### 🤖 Cursor AI
> This behavior typically indicates that either:
> 1. The payload returned by the previous tool execution isn't being appended to the `ChatSession` history correctly, making Gemini think its previous tool call failed or wasn't processed.
> 2. Gemini 3 Flash's system instructions aren't emphasizing task decomposition.
> 
> Let's inspect the agent's turn-handling implementation in `agent.py`. Can you share your current execution loop where you yield `ToolResponse` payloads back to the model?

### 👤 Human (Ankur)
> "Here is my loop: I catch the `function_calls` from the model, execute them async via the MCP client, but I noticed I am appending them as a plain user turn text block inside the history list instead of a proper `Part.function_response` block."

### 🤖 Cursor AI
> That is exactly why it is thrashing. Gemini tracks state based on symmetric structural history. If it emits a `function_call` block, it *must* receive a matching `function_response` block in the next turn. Treating it as standard user message history wipes out its context awareness.
>
> Let's modify the core execution block in `agent.py` to correctly format the model interaction lifecycle:
>
> ```python
> # Correcting the agent multi-turn execution step
> response = await model.generate_content(contents=chat_history)
> 
> if response.function_calls:
>     # 1. Append the model's intent to call the tool
>     chat_history.append(response.candidates[0].content)
>     
>     for function_call in response.function_calls:
>         # 2. Execute via GitHub MCP
>         mcp_result = await mcp_client.execute_tool(function_call.name, function_call.args)
>         
>         # 3. Create structural FunctionResponse Part
>         response_part = genai.types.Part.from_function_response(
>             name=function_call.name,
>             response={'result': mcp_result}
>         )
>         
>         # 4. Append as a dedicated tool role response
>         chat_history.append(genai.types.Content(role="function", parts=[response_part]))
> ```
> This guarantees that Gemini recognizes the data came from the system's runtime environment, instantly breaking the hallucination loop.

---

## 🎯 Key Takeaways & Architecture Summary
By utilizing Cursor alongside deep architectural oversight, the development lifecycle was highly optimized:
* **The AI accelerated:** Boilerplate code generation for JSON-RPC async communication, schema generation, and tool wrapping.
* **The Human engineered:** Ensured compatibility between divergent platform standards (JSON-Schema vs. Google Generative AI typing constraints) and maintained deterministic behavior in the multi-turn agentic loop.
