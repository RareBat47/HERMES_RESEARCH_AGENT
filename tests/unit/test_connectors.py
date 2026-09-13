import pytest
from src.connectors.arxiv_connector import ArxivConnector
from src.connectors.base import generate_bibtex_key
from src.connectors.crossref_connector import CrossrefConnector
from src.connectors.semantic_scholar import SemanticScholarConnector


def test_generate_bibtex_key():
    key = generate_bibtex_key("Ashish Vaswani", 2017, "Attention Is All You Need")
    assert key == "Vaswani2017Attention"

    key2 = generate_bibtex_key("Yann LeCun", 2015, "Deep learning")
    assert key2 == "LeCun2015Deep"

    key3 = generate_bibtex_key("", None, "")
    assert key3 == "Anonymous2024Paper"


def test_arxiv_feed_parsing():
    sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
        <entry>
            <id>http://arxiv.org/abs/1706.03762v7</id>
            <published>2017-06-12T17:57:34Z</published>
            <title>Attention Is All You Need</title>
            <summary>The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.</summary>
            <author><name>Ashish Vaswani</name></author>
            <author><name>Noam Shazeer</name></author>
            <link title="pdf" href="http://arxiv.org/pdf/1706.03762v7" rel="related" type="application/pdf"/>
            <arxiv:doi>10.5555/3295222.3295349</arxiv:doi>
        </entry>
    </feed>
    """
    connector = ArxivConnector()
    papers = connector._parse_feed(sample_xml)
    assert len(papers) == 1
    p = papers[0]
    assert p.bibtex_key == "Vaswani2017Attention"
    assert p.arxiv_id == "1706.03762v7"
    assert len(p.authors) == 2
    assert p.authors[0].name == "Ashish Vaswani"
    assert p.year == 2017
    assert p.pdf_url == "http://arxiv.org/pdf/1706.03762v7"


def test_semantic_scholar_model_conversion():
    connector = SemanticScholarConnector()
    sample_data = {
        "title": "Language Models are Few-Shot Learners",
        "authors": [{"name": "Tom B. Brown"}, {"name": "Benjamin Mann"}],
        "year": 2020,
        "venue": "NeurIPS",
        "citationCount": 15000,
        "externalIds": {"ArXiv": "2005.14165", "DOI": "10.48550/arXiv.2005.14165"},
        "openAccessPdf": {"url": "https://arxiv.org/pdf/2005.14165.pdf"},
        "abstract": "Recent work has demonstrated substantial gains on many NLP tasks and benchmarks.",
    }
    paper = connector._convert_to_model(sample_data)
    assert paper is not None
    assert paper.bibtex_key == "Brown2020Language"
    assert paper.year == 2020
    assert paper.citation_count == 15000
    assert paper.arxiv_id == "2005.14165"


def test_openalex_model_conversion():
    from src.connectors.openalex_connector import OpenAlexConnector
    connector = OpenAlexConnector()
    sample_item = {
        "title": "Deep Residual Learning for Image Recognition",
        "authorships": [{"author": {"display_name": "Kaiming He"}}],
        "publication_year": 2016,
        "cited_by_count": 180000,
        "doi": "https://doi.org/10.1109/CVPR.2016.90",
        "abstract_inverted_index": {"Deeper": [0], "neural": [1], "networks": [2], "are": [3], "difficult": [4], "to": [5], "train.": [6]},
        "primary_location": {"source": {"display_name": "CVPR"}, "pdf_url": "https://arxiv.org/pdf/1512.03385.pdf"},
        "ids": {"openalex": "https://openalex.org/W2164472856"},
    }
    paper = connector._convert_to_model(sample_item)
    assert paper is not None
    assert paper.bibtex_key == "He2016Deep"
    assert paper.year == 2016
    assert paper.citation_count == 180000
    assert paper.venue == "CVPR"
    assert "Deeper neural networks" in paper.abstract
    assert paper.doi == "10.1109/CVPR.2016.90"

