import os
from textwrap import dedent
from typing import Any

from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.memory import MemorySaver

GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/"
MODEL_ID = "gemini-3.5-flash"  # Supported stable production target for tool-calling

SYSTEM_PROMPT = dedent("""
    You are a GitHub Intelligence Agent with access to GitHub's full API through MCP tools.

    You can help with:
    - Searching and discovering repositories, users, code, issues, and pull requests
    - Profiling GitHub users and their most notable projects
    - Summarising open issues, pull requests, and releases for any repository
    - Analysing trends across GitHub (top repos, active projects, popular topics)
    - Exploring codebases and understanding project structure and activity

    When given a task:
    1. Use search_tools to dynamically find the right tools for the job
    2. Call the appropriate tools with precise, well-formed parameters
    3. Synthesise the results into a clear, well-structured response

    If a tool call fails, analyse the cause, adapt your approach, and retry with
    a different strategy. Persist until the task is complete.

    Do not narrate your process. Output only the final answer.
""")


async def build_agent(
    github_pat: str, gemini_api_key: str, streaming: bool = False
) -> Any:
    """Build and return a LangChain/LangGraph GitHub Intelligence Agent.

    Args:
        github_pat: GitHub Personal Access Token (read-only permissions are enough)
        gemini_api_key: Google AI Gemini API key
        streaming: Boolean toggle indicating if token serialization stream events are expected
    """
    # Enforce token binding to the system scope required by standard transport providers
    os.environ["GITHUB_PAT"] = github_pat
    os.environ["GOOGLE_API_KEY"] = gemini_api_key

    # Connect to the remote HTTP/SSE MCP server
    # MultiServerMCPClient handles headers via 'http' or 'sse' transport keys
    client = MultiServerMCPClient(
        {
            "github": {
                "transport": "http",
                "url": GITHUB_MCP_URL,
                "headers": {"Authorization": f"Bearer {github_pat}"},
            }
        }
    )

    # Compile and resolve remote schemas into LangChain BaseTools
    tools = await client.get_tools()

    # Initialize the Gemini LLM
    model = ChatGoogleGenerativeAI(model=MODEL_ID, temperature=0, streaming=streaming)

    # Instantiate LangGraph's native short-term conversation thread persistency state tracking
    memory = MemorySaver()
    # Construct the ReAct Agent Graph
    agent = create_agent(
        model=model, tools=tools, system_prompt=SYSTEM_PROMPT, checkpointer=memory
    )

    return agent
