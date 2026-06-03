from agent import text_from_stream_chunk


class _ChunkWithStrContent:
    content = "hello"


class _ChunkWithListContent:
    content = [{"type": "text", "text": "world"}]


def test_text_from_stream_chunk_string_content():
    assert text_from_stream_chunk(_ChunkWithStrContent()) == "hello"


def test_text_from_stream_chunk_list_content():
    assert text_from_stream_chunk(_ChunkWithListContent()) == "world"
    assert text_from_stream_chunk([{"type": "text", "text": "raw"}]) == "raw"


def test_text_from_stream_chunk_empty():
    assert text_from_stream_chunk({}) == ""
