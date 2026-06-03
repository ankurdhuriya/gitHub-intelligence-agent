# app.py
import asyncio
import os
import sys

import streamlit as st
from dotenv import load_dotenv

from agent import build_agent

load_dotenv()

st.set_page_config(
    page_title="GitHub Intelligence Agent", page_icon="🐙", layout="wide"
)

# -------------------------------------------------------------------
# Sidebar Setup
# -------------------------------------------------------------------
with st.sidebar:
    st.subheader("🐙 Session Stats")
    col1, col2 = st.columns(2)
    col1.metric(label="Queries", value=st.session_state.get("query_count", 0))
    col2.metric(label="Tools Used", value=st.session_state.get("tools_count", 0))

    st.markdown("---")
    st.subheader("Quick queries")

    presets = [
        "🔥 Top 5 repos by karpathy",
        "🐛 Open issues in huggingface/transformers",
        "🚀 What has Microsoft shipped on GitHub lately?",
        "📈 Trending Python AI repos by stars",
    ]

    chosen_preset = None
    for preset in presets:
        if st.button(preset):
            chosen_preset = preset[2:]

    st.markdown("---")
    if st.button("🗑️ Clear conversation"):
        st.session_state.messages = []
        st.rerun()

# -------------------------------------------------------------------
# App Interface Layout
# -------------------------------------------------------------------
st.title("🐙 GitHub Intelligence Agent")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "query_count" not in st.session_state:
    st.session_state.query_count = 0
if "tools_count" not in st.session_state:
    st.session_state.tools_count = 0

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_query = st.chat_input("Ask anything about GitHub...")
if chosen_preset:
    user_query = chosen_preset

if user_query:
    st.session_state.query_count += 1
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    with st.chat_message("assistant"):
        status_placeholder = st.empty()
        response_placeholder = st.empty()

        status_placeholder.markdown("🔍 *Initializing connection to server...*")

        async def stream_agent():
            github_pat = os.getenv("GITHUB_PAT")
            gemini_key = os.getenv("GOOGLE_API_KEY")

            print(f"\n[STDOUT DEBUG] --- New Query Triggered: '{user_query}' ---")
            print(f"[STDOUT DEBUG] GITHUB_PAT Found: {bool(github_pat)}")
            print(f"[STDOUT DEBUG] GOOGLE_API_KEY Found: {bool(gemini_key)}")

            if not github_pat or not gemini_key:
                print("[STDOUT DEBUG] ERROR: Missing environment credentials!")
                response_placeholder.error(
                    "Error: Missing credentials inside .env file."
                )
                return ""

            try:
                print("[STDOUT DEBUG] Calling build_agent()...")
                agent = await build_agent(
                    github_pat=github_pat, gemini_api_key=gemini_key, streaming=True
                )
                print("[STDOUT DEBUG] build_agent() succeeded. Graph generated.")
            except Exception as e:
                print(f"[STDOUT DEBUG] FATAL EXCEPTION during compilation: {e}")
                response_placeholder.error(f"Compilation Failed: {e}")
                return ""

            inputs = {"messages": [("user", user_query)]}
            config = {"configurable": {"thread_id": "streamlit_session_thread"}}
            full_response = ""

            try:
                print("[STDOUT DEBUG] Invoking astream_events engine loop...")
                async for event in agent.astream_events(inputs, config, version="v2"):
                    kind = event["event"]
                    name = event.get("name", "Unknown")

                    # Print structural updates to terminal window to track progress
                    print(
                        f"[STDOUT DEBUG] Event received -> Kind: {kind} | Node Name: {name}"
                    )

                    if kind == "on_chat_model_start":
                        print("[STDOUT DEBUG] Gemini LLM started thinking...")
                        status_placeholder.empty()

                    if kind == "on_tool_start":
                        print(
                            f"[STDOUT DEBUG] 🛠️ Executing GitHub MCP tool: {name} with inputs: {event['data'].get('input')}"
                        )
                        status_placeholder.markdown(
                            f"🛠️ *Executing GitHub API Tool: `{name}`...*"
                        )
                        st.session_state.tools_count += 1

                    if kind == "on_tool_end":
                        print(f"[STDOUT DEBUG] ✅ Tool {name} finished execution.")
                        status_placeholder.markdown("📝 *Processing tool results...*")

                    if kind == "on_chat_model_stream":
                        chunk = event["data"]["chunk"]
                        text_found = ""

                        # Debug text-extraction paths
                        if hasattr(chunk, "content") and chunk.content:
                            if isinstance(chunk.content, str):
                                text_found = chunk.content
                            elif isinstance(chunk.content, list):
                                for part in chunk.content:
                                    if (
                                        isinstance(part, dict)
                                        and part.get("type") == "text"
                                    ):
                                        text_found += part.get("text", "")
                        elif isinstance(chunk, list):
                            for part in chunk:
                                if (
                                    isinstance(part, dict)
                                    and part.get("type") == "text"
                                ):
                                    text_found += part.get("text", "")

                        if text_found:
                            # Print raw tokens to stdout console as they arrive
                            sys.stdout.write(text_found)
                            sys.stdout.flush()

                            full_response += text_found
                            response_placeholder.markdown(full_response + "▌")

                print(
                    f"\n[STDOUT DEBUG] Execution cycle complete. Final response length: {len(full_response)}"
                )
            except Exception as e:
                print(f"\n[STDOUT DEBUG] RUNTIME ERROR during stream execution: {e}")
                response_placeholder.error(f"Runtime Streaming Error: {e}")

            response_placeholder.markdown(full_response)
            return full_response

        final_text = asyncio.run(stream_agent())

        if final_text:
            st.session_state.messages.append(
                {"role": "assistant", "content": final_text}
            )
            st.rerun()
