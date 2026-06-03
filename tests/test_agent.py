import os

import pytest


# ==========================================
# 1. Environment & Sanity Tests
# ==========================================
def test_environment_variables_are_present():
    """
    Ensures that environment variables are loaded properly.
    This works locally via pytest-dotenv (.env) and in CI via GitHub Secrets.
    """
    openai_key = os.getenv("GOOGLE_API_KEY")
    github_pat = os.getenv("GITHUB_PAT")

    assert openai_key is not None, "GOOGLE_API_KEY is missing from the environment"
    assert github_pat is not None, "GITHUB_PAT is missing from the environment"

    # Ensure they aren't empty strings
    assert len(openai_key) > 0
    assert len(github_pat) > 0


# ==========================================
# 2. Async Dummy Tests (Simulating LangChain Agent)
# ==========================================
async def mock_agent_execution(prompt: str) -> str:
    """A dummy async function mimicking an asynchronous LangChain agent run."""
    if not prompt:
        raise ValueError("Prompt cannot be empty")
    return f"Agent processed: {prompt}"


@pytest.mark.asyncio
async def test_async_agent_behavior():
    """Verifies that pytest-asyncio handles async agent patterns cleanly across Python 3.11+."""
    response = await mock_agent_execution("Analyze repository layout")
    assert "Analyze repository layout" in response


@pytest.mark.asyncio
async def test_async_agent_exception():
    """Verifies async error handling inside the agent architecture."""
    with pytest.raises(ValueError, match="Prompt cannot be empty"):
        await mock_agent_execution("")


# ==========================================
# 3. Mocking Test (Simulating GitHub API calls)
# ==========================================
def get_github_repo_tags(token: str) -> list[str]:
    """Dummy function simulating an external network call to GitHub API."""
    if not token:
        return []
    # This would normally make an HTTP request using requests or a GitHub library
    return ["v1.0.0", "v1.1.0"]


def test_github_api_mocking(mocker):
    """
    Uses pytest-mock to simulate a GitHub API response.
    This ensures tests don't make real network calls or consume API rate limits during CI.
    """
    # Mocking the function to avoid hit limits or using internet connection
    mock_fetch = mocker.patch(
        "test_agent.get_github_repo_tags", return_value=["mocked-tag-v3"]
    )

    tags = mock_fetch("owner/repo", token="dummy-pat")

    assert tags == ["mocked-tag-v3"]
    mock_fetch.assert_called_once_with("owner/repo", token="dummy-pat")
