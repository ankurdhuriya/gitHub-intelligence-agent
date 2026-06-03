"""Arize AX OpenTelemetry setup.

Must be imported before any ``langchain`` / ``langgraph`` module (see ``app.py``).
"""

import os

_initialized = False


def init_observability() -> bool:
    """Register OTLP export to Arize AX and instrument LangChain/LangGraph."""
    global _initialized
    if _initialized:
        return True

    space_id = os.getenv("ARIZE_SPACE_ID")
    api_key = os.getenv("ARIZE_API_KEY")
    if not space_id or not api_key:
        return False

    from arize.otel import register
    from openinference.instrumentation.langchain import LangChainInstrumentor

    project_name = os.getenv("ARIZE_PROJECT_NAME", "github-intelligence-agent")

    tracer_provider = register(
        space_id=space_id,
        api_key=api_key,
        project_name=project_name,
        verbose=False,
    )
    LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
    _initialized = True
    return True
