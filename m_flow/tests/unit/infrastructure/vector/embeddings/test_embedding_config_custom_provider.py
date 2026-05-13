from __future__ import annotations

from m_flow.adapters.vector.embeddings.config import EmbeddingConfig


def test_embedding_config_respects_custom_dimensions_and_batch_size():
    cfg = EmbeddingConfig(
        embedding_provider="custom",
        embedding_model="openai/text-embedding-v4",
        embedding_dimensions=1024,
        embedding_batch_size=10,
        embedding_endpoint="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    assert cfg.embedding_provider == "custom"
    assert cfg.embedding_model == "openai/text-embedding-v4"
    assert cfg.embedding_dimensions == 1024
    assert cfg.embedding_batch_size == 10
    assert cfg.embedding_endpoint == "https://dashscope.aliyuncs.com/compatible-mode/v1"
