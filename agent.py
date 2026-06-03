import os
from collections.abc import Callable
from dataclasses import dataclass
from textwrap import dedent
from typing import Any, Protocol

from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from checkpointing import create_checkpointer

GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/"
MODEL_ID = "gemini-3.5-flash"
DEFAULT_THREAD_ID = "streamlit_session_thread"

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


class AgentGraph(Protocol):
    def astream_events(
        self,
        input: Any,
        config: Any,
        *,
        version: str,
    ) -> Any: ...


@dataclass(frozen=True)
class AgentConfig:
    thread_id: str = DEFAULT_THREAD_ID


def get_required_credentials() -> tuple[str, str]:
    """Return (GITHUB_PAT, GOOGLE_API_KEY) from the environment."""
    github_pat = os.getenv("GITHUB_PAT")
    gemini_api_key = os.getenv("GOOGLE_API_KEY")
    if not github_pat or not gemini_api_key:
        raise ValueError(
            "Missing credentials: set GITHUB_PAT and GOOGLE_API_KEY in your .env file."
        )
    return github_pat, gemini_api_key


def _create_mcp_client(github_pat: str) -> MultiServerMCPClient:
    return MultiServerMCPClient(
        {
            "github": {
                "transport": "http",
                "url": GITHUB_MCP_URL,
                "headers": {"Authorization": f"Bearer {github_pat}"},
            }
        }
    )


def text_from_stream_chunk(chunk: Any) -> str:
    """Extract plain text from a Gemini/LangChain streaming chunk."""
    if hasattr(chunk, "content") and chunk.content:
        if isinstance(chunk.content, str):
            return chunk.content
        if isinstance(chunk.content, list):
            return _text_from_content_parts(chunk.content)

    if isinstance(chunk, list):
        return _text_from_content_parts(chunk)

    return ""


def _text_from_content_parts(parts: list[Any]) -> str:
    text = ""
    for part in parts:
        if isinstance(part, dict) and part.get("type") == "text":
            text += part.get("text", "")
    return text


async def build_agent(
    github_pat: str,
    gemini_api_key: str,
    *,
    checkpointer: AsyncPostgresSaver | None = None,
    streaming: bool = False,
) -> AgentGraph:
    """Build and return a LangChain/LangGraph GitHub Intelligence Agent."""
    client = _create_mcp_client(github_pat)
    tools = await client.get_tools()

    model = ChatGoogleGenerativeAI(
        model=MODEL_ID,
        temperature=0,
        streaming=streaming,
        google_api_key=gemini_api_key,
    )

    if checkpointer is None:
        checkpointer = await create_checkpointer()

    return create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )


async def stream_agent_response(
    agent: AgentGraph,
    query: str,
    *,
    thread_id: str = DEFAULT_THREAD_ID,
    on_status: Callable[[str], None] | None = None,
    on_token: Callable[[str], None] | None = None,
    on_tool_start: Callable[[str], None] | None = None,
) -> str:
    """Stream an agent run and return the full assistant text."""
    inputs = {"messages": [("user", query)]}
    config = {"configurable": {"thread_id": thread_id}}
    full_response = ""

    async for event in agent.astream_events(inputs, config, version="v2"):
        kind = event["event"]
        name = event.get("name", "Unknown")

        if kind == "on_chat_model_start" and on_status:
            on_status("")

        if kind == "on_tool_start":
            if on_tool_start:
                on_tool_start(name)
            if on_status:
                on_status(f"🛠️ *Executing GitHub API Tool: `{name}`...*")

        if kind == "on_tool_end" and on_status:
            on_status("📝 *Processing tool results...*")

        if kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            text = text_from_stream_chunk(chunk)
            if text:
                full_response += text
                if on_token:
                    on_token(text)

    return full_response
