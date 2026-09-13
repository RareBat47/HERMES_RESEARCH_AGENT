from src.common.models import PaperSectionContent
from src.ingestion.chunker import AcademicChunker
from src.ingestion.grobid_parser import GrobidParser


def test_grobid_tei_parsing():
    sample_tei = """<TEI xmlns="http://www.tei-c.org/ns/1.0">
        <teiHeader>
            <profileDesc>
                <abstract>
                    <p>This is the experimental abstract demonstrating neural networks.</p>
                </abstract>
            </profileDesc>
        </teiHeader>
        <text>
            <body>
                <div>
                    <head>1. Introduction</head>
                    <p>Deep learning has revolutionized artificial intelligence.</p>
                    <p>Recent advances show immense scaling potentials.</p>
                </div>
                <div>
                    <head>2. Methodology and Framework</head>
                    <p>We propose an orthogonal self-attention layer.</p>
                </div>
                <div>
                    <head>3. Limitations and Future Work</head>
                    <p>Our model requires significant memory bandwidth.</p>
                </div>
            </body>
        </text>
    </TEI>
    """
    parser = GrobidParser()
    sections = parser._parse_tei_xml(sample_tei)
    assert len(sections) == 4

    assert sections[0].section_name == "Abstract"
    assert "experimental abstract" in sections[0].text_content

    assert sections[1].section_name == "Introduction"
    assert sections[1].heading == "1. Introduction"

    assert sections[2].section_name == "Methods"
    assert sections[3].section_name == "Limitations"


def test_academic_chunker():
    chunker = AcademicChunker(target_chunk_size=100, overlap_size=30)
    section = PaperSectionContent(
        section_name="Methods",
        heading="2.1 Architecture",
        text_content="Paragraph one describes the initial setup.\n\nParagraph two details the gradient optimizer and learning rate decay schedule.\n\nParagraph three discusses batch size and regularizations.",
        page_number=3,
    )
    chunks = chunker.chunk_section(section, paper_id=42, bibtex_key="Vaswani2017Attention")
    assert len(chunks) >= 2
    for c in chunks:
        assert c["paper_id"] == 42
        assert c["bibtex_key"] == "Vaswani2017Attention"
        assert c["section_name"] == "Methods"
        assert "text_content" in c
