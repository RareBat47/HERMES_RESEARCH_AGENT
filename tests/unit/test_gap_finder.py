import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agent.cohere_client import CohereClient
from src.gap_finder.analyzer import ResearchGapAnalyzer


@pytest.fixture
def sample_papers():
    return [
        {
            "bibtex_key": "Vaswani2017",
            "title": "Attention Is All You Need",
            "abstract": "We propose the Transformer, a model architecture eschewing recurrence and relying entirely on an attention mechanism to draw global dependencies.",
            "year": 2017,
            "notes": [
                {
                    "datasets": ["WMT 2014 English-to-German", "WMT 2014 English-to-French"],
                    "metrics": ["BLEU"],
                    "limitations": "Quadratic memory complexity with sequence length",
                    "method_details": "Multi-head scaled dot-product self-attention",
                }
            ],
        },
        {
            "bibtex_key": "Dao2022Flash",
            "title": "FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness",
            "abstract": "We introduce FlashAttention, an IO-aware exact attention algorithm that uses tiling to reduce the number of memory reads/writes between GPU HBM and SRAM.",
            "year": 2022,
            "notes": [
                {
                    "datasets": ["Long Range Arena", "WikiText-103"],
                    "metrics": ["Speedup", "Perplexity", "Accuracy"],
                    "limitations": "Hardware-specific CUDA optimizations needed",
                    "method_details": "Tiling and recomputation in SRAM",
                }
            ],
        },
        {
            "bibtex_key": "Beltagy2020Longformer",
            "title": "Longformer: The Long-Document Transformer",
            "abstract": "Longformer uses an attention mechanism that scales linearly with sequence length, making it easy to process documents of thousands of tokens.",
            "year": 2020,
            "notes": [
                {
                    "datasets": ["WikiHop", "triviaQA"],
                    "metrics": ["F1", "BPC"],
                    "limitations": "Windowed local attention drops global context",
                    "method_details": "Sliding window local attention combined with task-motivated global attention",
                }
            ],
        },
        {
            "bibtex_key": "Gu2023Mamba",
            "title": "Mamba: Linear-Time Sequence Modeling with Selective State Spaces",
            "abstract": "State space models (SSMs) with linear-time sequence modeling have emerged as a promising alternative to Transformers. We propose selective state spaces.",
            "year": 2023,
            "notes": [
                {
                    "datasets": ["The Pile", "LAMBADA"],
                    "metrics": ["Perplexity", "Throughput"],
                    "limitations": "Information bottleneck on multi-hop associative recall",
                    "method_details": "Hardware-aware selection mechanism for continuous state space models",
                }
            ],
        },
    ]


@pytest.mark.asyncio
async def test_gap_analyzer_synthetic_dataset(sample_papers):
    mock_cohere = MagicMock(spec=CohereClient)
    ret_val = """{
        "top_gaps": [
            "Trade-off between exact quadratic attention and sub-quadratic state space models in multi-hop reasoning",
            "Evaluation gap on extreme streaming context (>10M tokens)",
            "Lack of standardized hardware-independent IO-aware benchmarks"
        ],
        "proposed_experiments": [
            "Benchmark Mamba vs FlashAttention-2 on 500k context needle-in-a-haystack tasks"
        ],
        "recommended_searches": [
            "selective state spaces associative recall",
            "hardware-aware sub-quadratic attention"
        ]
    }"""
    mock_cohere.chat = AsyncMock(return_value=ret_val)
    mock_cohere.chat_completion = AsyncMock(return_value=ret_val)

    analyzer = ResearchGapAnalyzer(cohere_client=mock_cohere)
    results = await analyzer.analyze_gaps(
        papers=sample_papers,
        project_goal="Scalable long-context language modeling",
    )

    assert results["total_papers_analyzed"] == 4
    assert len(results["clusters"]) >= 1
    assert "synthesized_gaps" in results
    assert len(results["synthesized_gaps"]) >= 3
    assert len(results["proposed_experiments"]) >= 1
    assert len(results["recommended_searches"]) >= 1
    assert "missing_signals" in results
    assert len(results["missing_signals"]["datasets"]) >= 1
    assert len(results["missing_signals"]["limitations"]) >= 1


@pytest.mark.asyncio
async def test_gap_analyzer_empty_library():
    mock_cohere = MagicMock(spec=CohereClient)
    analyzer = ResearchGapAnalyzer(cohere_client=mock_cohere)
    results = await analyzer.analyze_gaps(papers=[])

    assert results["clusters"] == []
    assert len(results["synthesized_gaps"]) >= 1
    assert "empty" in results["synthesized_gaps"][0].lower()
