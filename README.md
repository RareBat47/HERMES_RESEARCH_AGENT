# 🏛️ HERMES_RESEARCH_AGENT

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![Qdrant](https://img.shields.io/badge/Qdrant-v1.11+-dc2626.svg)](https://qdrant.tech/)
[![GROBID](https://img.shields.io/badge/GROBID-0.8.1-orange.svg)](https://grobid.readthedocs.io/)
[![Discord.py](https://img.shields.io/badge/Discord.py-v2.3+-5865F2.svg)](https://discordpy.readthedocs.io/)
[![Docker Compose](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://docker.com)

**HERMES_RESEARCH_AGENT** is an academic-first, production-ready research assistant engineered for a 2-researcher Discord laboratory. It supports up to 6 months of continuous scientific research: multi-engine literature discovery, dual-layer parsing (GROBID TEI-XML + PyMuPDF), chunk-level semantic vector indexing in Qdrant, long-term project memory, multi-agent synthesis, and **strictly evidence-grounded RAG** where every claim must be substantiated with exact BibTeX keys, quotes, and section/page hints.

---

## 🎯 Hard Architectural Guarantees

1. **Evidence-Grounded RAG with Strict Citations**:
   - Every answer to `/ask` is strictly grounded in passages retrieved from your library.
   - Outputs include `\cite{BibKey}`, exact quote spans, section names, and page numbers.
   - If evidence is absent, Hermes explicitly refuses to over-claim, states the evidence gap, and proposes targeted search queries.
2. **Chunk-Level Indexing**:
   - Explicit `paper_chunks` records in PostgreSQL (tracking `char_start`, `char_end`, `page_number`, `chunk_index`).
   - Vectors indexed in Qdrant with dense embeddings and optional Cross-Encoder reranking.
3. **Dual-Layer Scientific Extraction**:
   - Layer 1 (Primary): **GROBID** Docker container for academic TEI XML hierarchy.
   - Layer 2 (Fallback): Heuristic **PyMuPDF** (`fitz`) section parser.
4. **2-Person Security Allowlist**:
   - The Discord bot enforces strict allowlist authentication via `USER1_ID` and `USER2_ID`. Unrecognized users cannot issue commands.
5. **Universal Execution Modes**:
   - **Docker Compose Mode**: 8 microservices (`postgres`, `qdrant`, `redis`, `minio`, `grobid`, `api`, `worker`, `discord-bot`).
   - **Local Mode (Docker daemon stopped)**: Runs directly on Python 3.12 with SQLite and embedded Qdrant.

---

## 🏗️ System Architecture & Data Flow

```mermaid
sequenceDiagram
    autonumber
    actor R as Researcher (Discord)
    participant B as Discord Bot
    participant API as FastAPI Gateway
    participant W as Celery Ingestion Worker
    participant G as GROBID / PyMuPDF
    participant DB as Postgres (Metadata & Chunks)
    participant QD as Qdrant Vector Store
    participant LLM as AgentRouter / LLM Gateway

    R->>B: /search query:"sparse attention" source:all
    B->>API: POST /search
    API-->>B: Deduplicated results from arXiv, S2, PubMed, OpenAlex
    B-->>R: Rich Embed + Interactive "Add to Library" Button

    R->>B: Click "Add to Library" or /add_paper identifier:"1706.03762"
    B->>API: POST /papers/ingest
    API->>W: Enqueue Ingestion Job (tasks.ingest_paper)
    W->>W: Download PDF (rate-limited, size limits)
    W->>G: Parse TEI XML sections (Abstract, Methods, Results, Limitations)
    W->>DB: Store Paper, Authors, Sections, and explicit PaperChunks
    W->>QD: Embed and upsert chunk vectors + offsets
    W->>LLM: ReaderAgent extracts structured note & evidence quotes
    W->>DB: Update IngestionJob (status=completed)
    B-->>R: Discord Progress Notification (100% Parsed & Indexed)

    R->>B: /ask question:"What is the complexity per layer of self-attention?"
    B->>API: POST /agent/ask
    API->>QD: Retrieve top-k semantic chunks
    API->>LLM: GroundedQAAgent strictly verifies claim vs quotes
    API-->>B: GroundedAnswer (answer text, \cite{BibKey}, exact quote, p. hint)
    B-->>R: Evidence-grounded card with verbatim citations
```

---

## ⚡ Quickstart with Docker Compose (Production / VM)

Deploy on any Linux VM or local Docker setup in 3 minutes:

```bash
# 1. Clone repository
git clone https://github.com/your-org/hermes-research-agent.git
cd hermes-research-agent

# 2. Configure environment
cp .env.example .env
nano .env   # Provide DISCORD_BOT_TOKEN, USER1_ID, USER2_ID, and LLM_API_KEY

# 3. Launch the full 8-service stack
docker compose up -d --build

# 4. View container status
docker compose ps
```

Services started:
- `postgres` (Port 5432)
- `qdrant` (Port 6333, Dashboard at `/dashboard`)
- `redis` (Port 6379)
- `minio` (Port 9000, Console at `:9001`)
- `grobid` (Port 8070)
- `api` (FastAPI at `:8000/docs`)
- `worker` (Celery background queue)
- `discord-bot` (Discord.py client)

---

## 💻 Local Development Without Docker (Daemon Stopped)

When Docker is offline, all components run smoothly on bare Python 3.12:

### 1. Install Dependencies
```bash
pip install -e ".[dev]"
```

### 2. Initialize Database & Run Tests
```bash
python scripts/init_db.py
python -m pytest tests/unit -v
```

### 3. Run CLI Utilities Directly
```bash
# 1. Search literature across arXiv, S2, PubMed, OpenAlex
python scripts/test_search.py "transformers for time series"

# 2. Ingest and parse a paper into local database
python scripts/ingest_paper.py "1706.03762"

# 3. Ask question against library chunks
python scripts/ask_library.py "How does self-attention operate?"
```

### 4. Start Local API & Discord Bot
```bash
# Terminal 1: API
python -m uvicorn src.api.main:app --port 8000 --reload

# Terminal 2: Discord Bot
python -m src.discord_bot.bot
```

---

## 💬 Discord Slash Command Reference

| Command | Arguments | Description |
| :--- | :--- | :--- |
| `/project` | `action: create \| switch \| truth`, `name` | Create projects, switch active context, or display shared truth & decision logs. |
| `/search` | `query`, `source: all \| arxiv \| semanticscholar \| pubmed`, `limit` | Live literature search with interactive pagination and `[📥 Add to Library]` button. |
| `/add_paper` | `identifier` (arXiv ID, DOI, URL, or PMID) | Ingests paper, downloads PDF, extracts TEI sections, indexes chunks, and notifies Discord. |
| `/library` | `action: recent \| find`, `query` | Browse indexed papers in library or search by keyword. |
| `/summarize` | `paper: BibKey`, `style: short \| deep` | Displays structured Reading Mode card (problem, idea, methods, results, limitations, quotes). |
| `/ask` | `question`, `scope: library` | Evidence-grounded QA citing exact `\cite{BibKey}`, quote spans, and section/page hints. |
| `/compare` | `papers: key1,key2`, `criteria` | Generates cross-paper comparison matrix and surfaces research gaps. |
| `/outline` | `topic`, `target: related work \| methods` | Produces structured academic manuscript outline with citation anchors. |
| `/draft` | `section`, `topic` | Drafts a formal manuscript section with strict BibTeX citations. |
| `/tasks` | `action: add \| list \| done`, `title` | Collaborative laboratory task board. |
| `/scratchpad`| `action: view \| add \| clear`, `note` | Private per-researcher scratchpad for ideation before sharing. |

---

## 🔧 Troubleshooting

### Problem: Docker daemon is stopped or cannot connect
- **Cause**: Docker Desktop is not running or Linux daemon is stopped.
- **Solution**: The Hermes codebase detects this and automatically switches to the embedded local Qdrant engine and SQLite database. Run `python -m pytest tests/unit -v` and run the FastAPI server locally (`uvicorn src.api.main:app --port 8000`).

### Problem: Discord bot displays "Access Denied"
- **Cause**: Your Discord user ID is not in `USER1_ID` or `USER2_ID` in `.env`.
- **Solution**: In Discord, enable *Developer Mode* (Settings -> Advanced -> Developer Mode). Right-click your profile and select *Copy User ID*. Paste into `.env` and restart the bot.

### Problem: Semantic Scholar returns status 429
- **Cause**: Public rate limits on api.semanticscholar.org.
- **Solution**: Hermes automatically falls back to arXiv and OpenAlex. For dedicated S2 bandwidth, add `SEMANTIC_SCHOLAR_API_KEY` in `.env`.

---

## 🧪 Automated Testing

Hermes includes a comprehensive unit test suite:
```bash
python -m pytest tests/unit -v
```

14 passing tests validate:
- BibTeX key standardization (`[Author][Year][Keyword]`)
- arXiv XML feed parsing & redirection handling
- Semantic Scholar and OpenAlex model conversions
- GROBID TEI XML section parsing
- Academic semantic chunker character offsets (`char_start`, `char_end`)
- Grounded QA with verbatim citation passages & unsupported claim fallbacks
- Database models: `PaperChunk`, `IngestionJob`, `Project`, and `UserScratchpad`
- Multi-agent state transitions (Planner, Writer, Critic)
