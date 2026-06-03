import asyncio

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

import observability  # noqa: E402, F401 — must run before langchain imports

observability.init_observability()

from agent import (  # noqa: E402
    build_agent,
    get_required_credentials,
    stream_agent_response,
)
from checkpointing import close_checkpointer, create_checkpointer  # noqa: E402

PRESETS = [
    "🔥 Top 5 repos by karpathy",
    "🐛 Open issues in huggingface/transformers",
    "🚀 What has Microsoft shipped on GitHub lately?",
    "📈 Trending Python AI repos by stars",
]
STREAMLIT_THREAD_ID = "streamlit_session_thread"


def _get_event_loop() -> asyncio.AbstractEventLoop:
    """Keep one event loop per Streamlit session (asyncio.run closes it each call)."""
    loop = st.session_state.get("event_loop")
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(close_checkpointer())
        st.session_state.event_loop = loop
        st.session_state.agent = None
        st.session_state.checkpointer = None
    return loop


def _run_async(coro):
    return _get_event_loop().run_until_complete(coro)


def _init_session_state() -> None:
    defaults = {
        "messages": [],
        "query_count": 0,
        "tools_count": 0,
        "agent": None,
        "checkpointer": None,
        "event_loop": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_sidebar() -> str | None:
    st.subheader("🐙 Session Stats")
    col1, col2 = st.columns(2)
    col1.metric(label="Queries", value=st.session_state.query_count)
    col2.metric(label="Tools Used", value=st.session_state.tools_count)

    st.markdown("---")
    st.subheader("Quick queries")

    chosen_preset = None
    for preset in PRESETS:
        if st.button(preset):
            chosen_preset = preset[2:]

    st.markdown("---")
    if st.button("🗑️ Clear conversation"):
        st.session_state.messages = []
        st.rerun()

    return chosen_preset


def render_message_history() -> None:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])


async def _get_or_create_checkpointer():
    if st.session_state.checkpointer is not None:
        return st.session_state.checkpointer

    checkpointer = await create_checkpointer()
    st.session_state.checkpointer = checkpointer
    return checkpointer


async def _get_or_create_agent():
    if st.session_state.agent is not None:
        return st.session_state.agent

    github_pat, gemini_key = get_required_credentials()
    checkpointer = await _get_or_create_checkpointer()
    agent = await build_agent(
        github_pat=github_pat,
        gemini_api_key=gemini_key,
        checkpointer=checkpointer,
        streaming=True,
    )
    st.session_state.agent = agent
    return agent


async def _stream_response(
    user_query: str, status_placeholder, response_placeholder
) -> str:
    status_placeholder.markdown("🔍 *Initializing connection to server...*")

    try:
        agent = await _get_or_create_agent()
    except ValueError as e:
        response_placeholder.error(str(e))
        return ""
    except Exception as e:
        response_placeholder.error(f"Compilation failed: {e}")
        return ""

    accumulated = ""

    def on_status(message: str) -> None:
        if message:
            status_placeholder.markdown(message)
        else:
            status_placeholder.empty()

    def on_tool_start(_name: str) -> None:
        st.session_state.tools_count += 1

    def on_token(token: str) -> None:
        nonlocal accumulated
        accumulated += token
        response_placeholder.markdown(accumulated + "▌")

    try:
        final_text = await stream_agent_response(
            agent,
            user_query,
            thread_id=STREAMLIT_THREAD_ID,
            on_status=on_status,
            on_token=on_token,
            on_tool_start=on_tool_start,
        )
    except Exception as e:
        response_placeholder.error(f"Runtime streaming error: {e}")
        return ""

    response_placeholder.markdown(final_text)
    return final_text


def handle_user_query(user_query: str) -> None:
    st.session_state.query_count += 1
    st.session_state.messages.append({"role": "user", "content": user_query})

    with st.chat_message("user"):
        st.markdown(user_query)

    with st.chat_message("assistant"):
        status_placeholder = st.empty()
        response_placeholder = st.empty()
        final_text = _run_async(
            _stream_response(user_query, status_placeholder, response_placeholder)
        )

    if final_text:
        st.session_state.messages.append({"role": "assistant", "content": final_text})
        st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="GitHub Intelligence Agent", page_icon="🐙", layout="wide"
    )
    _init_session_state()

    with st.sidebar:
        chosen_preset = render_sidebar()

    st.title("🐙 GitHub Intelligence Agent")
    render_message_history()

    user_query = st.chat_input("Ask anything about GitHub...")
    if chosen_preset:
        user_query = chosen_preset

    if user_query:
        handle_user_query(user_query)


main()
