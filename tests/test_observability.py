import observability


def test_init_observability_skips_without_credentials(monkeypatch):
    observability._initialized = False
    monkeypatch.delenv("ARIZE_SPACE_ID", raising=False)
    monkeypatch.delenv("ARIZE_API_KEY", raising=False)

    assert observability.init_observability() is False
    assert observability._initialized is False
