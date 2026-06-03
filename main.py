import asyncio
import os
import sys

from dotenv import load_dotenv

from agent import build_agent


async def execution_loop():
    # Load keys from local project .env file
    load_dotenv()

    github_pat = os.getenv("GITHUB_PAT")
    gemini_key = os.getenv("GOOGLE_API_KEY")

    if not github_pat or not gemini_key:
        print(
            "Error: Missing credentials inside your local environment variable allocations.",
            file=sys.stderr,
        )
        return

    print("🚀 Connecting to external GitHub MCP Server via SSE...")
    # Compile the agent architecture with streaming enabled
    agent = await build_agent(
        github_pat=github_pat, gemini_api_key=gemini_key, streaming=True
    )
    print("✅ Agent Compiled with GitHub Copilot toolsets successfully!")

    query = "Top five python projects on GitHub sorted by stars"
    print(f"\n💬 User Query: {query}\n")
    print("🤖 Agent Streaming Response:\n" + "=" * 40)

    # Dispatch data inputs to LangGraph engine using thread configuration markers
    inputs = {"messages": [("user", query)]}
    config = {"configurable": {"thread_id": "interactive_cli_session"}}

    # Intercept streaming event sequences natively generated from the LangGraph execution path
    async for event in agent.astream_events(inputs, config, version="v2"):
        kind = event["event"]

        # Capture raw LLM tokens as they are produced by the model node
        if kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]

            # Case 1: If chunk is a standard LangChain AIMessageChunk (has .content attribute)
            if hasattr(chunk, "content"):
                if isinstance(chunk.content, str) and chunk.content:
                    print(chunk.content, end="", flush=True)
                elif isinstance(chunk.content, list):
                    # Handle composite content blocks if Gemini returns a list structure
                    for part in chunk.content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            print(part.get("text", ""), end="", flush=True)

            # Case 2: If chunk arrives as a raw list of dictionaries (as seen in your output)
            elif isinstance(chunk, list):
                for part in chunk:
                    if isinstance(part, dict) and part.get("type") == "text":
                        print(part.get("text", ""), end="", flush=True)

    print("\n" + "=" * 40 + "\n🏁 Execution Finished.")


if __name__ == "__main__":
    # Safely kick off the async processing layer via the python runtime engine
    asyncio.run(execution_loop())
