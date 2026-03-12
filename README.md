# EduSecure Questionnaire Assistant

An AI-powered web app that automates vendor/compliance questionnaire responses by grounding every answer in your own reference documentation.

---

## Fictional Company: EduSecure

**Industry:** Education Technology (EdTech)

**Description:** EduSecure is a cloud-based learning management system (LMS) serving K-12 schools and universities across North America. We provide secure student data management, virtual classroom tools, assignment tracking, and parent-teacher communication. Our platform is used by 500+ educational institutions and handles sensitive student records under FERPA and COPPA compliance.

---

## What This Tool Does

When a prospect or partner sends a security/compliance questionnaire, filling it out manually is tedious and error-prone. This tool:

1. **Parses** the questionnaire (`.xlsx`, `.xls`, or `.csv`) into individual questions
2. **Indexes** internal reference documents (`.txt` / `.pdf`) using local embeddings + FAISS
3. **Generates** accurate answers using RAG (Groq LLM + retrieved context)
4. **Attaches citations** — source document name + exact evidence snippet per answer
5. **Lets you review and edit** answers inline before exporting
6. **Exports** a completed `.xlsx` with the original structure preserved, answers inserted, and citations included

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.11+) |
| Database | SQLite via SQLAlchemy ORM |
| LLM | Groq API — `llama-3.3-70b-versatile` (free tier) |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` — runs **locally**, no API needed |
| Vector search | FAISS `IndexFlatIP` (in-memory, rebuilt from DB on startup) |
| Auth | Session cookies (Starlette `SessionMiddleware`) + PBKDF2-HMAC-SHA256 |
| Frontend | Jinja2 server-rendered templates + vanilla HTML/CSS/JS |
| File parsing | `openpyxl` (xlsx), `xlrd` (xls), stdlib `csv` |

---

## Getting Started

### Prerequisites

- **Python 3.11+**
- **A free Groq API key** — get one at https://console.groq.com (no credit card required)
---

### Option A — One-command setup (recommended)

```bash
git clone <your-repo-url>
cd questionnaire-assistant
bash setup.sh
```

`setup.sh` does everything:
- Creates a Python virtual environment
- Installs all dependencies from `requirements.txt`
- Copies `.env.example` → `.env`
- Generates `sample_data/sample_questionnaire.xlsx`
- Initialises the SQLite database

Then open `.env` and set your key:
```
GROQ_API_KEY=gsk_...
```

---

### Option B — Manual steps

```bash
git clone <your-repo-url>
cd questionnaire-assistant

# 1. Virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Dependencies
pip install -r requirements.txt

# 3. Environment file
cp .env.example .env
# Open .env and set GROQ_API_KEY=gsk_...

# 4. Sample data + database
python create_sample_data.py    # generates sample_data/sample_questionnaire.xlsx
python -m app.init_db           # creates questionnaire.db
```

> **First run note:** `sentence-transformers` downloads the `all-MiniLM-L6-v2` model (~90 MB) on the first run only. Subsequent starts are instant.

---

### Run the app

```bash
source venv/bin/activate
python run.py
```

Open http://localhost:8000

---

## Usage

### 1. Sign Up / Log In
Create an account with email and password, then log in to reach the dashboard.

### 2. Upload Reference Documents
In the **Reference Documents** panel, upload `.txt` or `.pdf` source-of-truth files. Sample docs are in `sample_data/`. Each file is chunked and indexed immediately.

### 3. Create a Project and Upload a Questionnaire
Click **New Project**, name it, and upload your questionnaire (`.xlsx`, `.xls`, or `.csv`). The system auto-detects the question column and parses all rows.

> If no questions are detected, a re-upload form appears so you can try a different file.

### 4. Generate Answers
Click **Generate Answers**. For every question the pipeline:
- Embeds the question locally
- Retrieves the top-3 most relevant document chunks from FAISS
- Sends them to the Groq LLM to synthesise a grounded answer
- Attaches citations and a confidence score
- Falls back to `"Not found in references."` if nothing relevant is found

### 5. Review and Edit
Each answer shows its confidence badge, evidence snippet, and source document. Edit any answer inline — edited answers get an **Edited** badge.

### 6. Export
Click **Export Questionnaire** to download a completed `.xlsx` with the original structure preserved, answers alongside questions, and citations in a dedicated column.

---

## Features Implemented

### Core (Must-Have)
- [x] User authentication — signup, login, session management
- [x] Questionnaire upload and parsing — `.xlsx` / `.xls` / `.csv` with auto-column detection
- [x] Reference document upload and indexing — `.txt` and `.pdf`
- [x] AI-powered answer generation with RAG (Groq LLM + FAISS retrieval)
- [x] Citation tracking — source document name + evidence snippet per answer
- [x] `"Not found in references."` fallback when no relevant context exists
- [x] Review and inline edit interface
- [x] Export to `.xlsx` preserving original questionnaire structure

### Nice-to-Have (4 of 5 implemented)
- [x] **Confidence Score** — per-answer score (0–100%) shown as a colour-coded badge; included in the export
- [x] **Evidence Snippets** — exact retrieved chunk displayed under each citation in the review UI
- [x] **Partial Regeneration** — individual regenerate button per question; no need to redo the whole set
- [x] **Coverage Summary** — header bar shows total / answered / edited / unanswered counts at a glance
- [ ] Version History — not implemented

---

## Sample Data

| File | Description |
|---|---|
| `sample_data/security_policy.txt` | AES-256 encryption, TLS, MFA, SOC 2 Type II |
| `sample_data/privacy_policy.txt` | FERPA, COPPA, data retention, third-party sharing |
| `sample_data/infrastructure.txt` | AWS hosting, RDS, auto-scaling, DR targets |
| `sample_data/sample_questionnaire.xlsx` | 12-question vendor security assessment |

**Quick demo:** upload all three `.txt` files as Reference Documents, then create a project with `sample_questionnaire.xlsx`.

---

## Technical Details

### RAG Pipeline

1. **Chunking** — Docs split into ~500-character chunks with 100-character overlap
2. **Embedding** — Each chunk embedded locally with `all-MiniLM-L6-v2` (no API call, 384-dim vectors)
3. **Storage** — Embeddings persisted in SQLite; loaded into FAISS `IndexFlatIP` on startup via a background thread (non-blocking)
4. **Retrieval** — Question is embedded at query time; top-3 highest-cosine-similarity chunks retrieved
5. **Generation** — Chunks + question sent to `llama-3.3-70b-versatile` via Groq with a structured prompt
6. **Fallback** — If `GROQ_API_KEY` is absent or the API errors, the best-matching raw snippet is returned with `confidence = 0.4`

### Database Schema

| Table | Key Columns |
|---|---|
| `users` | id, email, hashed_password, full_name |
| `projects` | id, user_id, name, status, questionnaire_filename |
| `questions` | id, project_id, question_number, question_text, original_row_data (JSON) |
| `answers` | id, question_id, answer_text, citations (JSON), confidence_score, is_edited |
| `documents` | id, user_id, filename, file_path, file_type, file_size |
| `document_chunks` | id, document_id, chunk_text, embedding (bytes) |

### Security

- Passwords hashed with PBKDF2-HMAC-SHA256 + per-user random 16-byte salt (`hashlib` + `secrets`)
- Sessions via Starlette `SessionMiddleware` — signed `httponly` cookies, no client-side token storage
- SQL injection prevented by SQLAlchemy ORM parameterised queries
- File uploads restricted to an extension allowlist (`.txt`, `.pdf`, `.xlsx`, `.xls`, `.csv`)

---

## Useful Commands

```bash
# Start the server
source venv/bin/activate && python run.py

# Wipe DB + uploads and start completely fresh
python cleanup.py

# Recreate sample data after a cleanup
python create_sample_data.py && python -m app.init_db
```

---

## Assumptions

1. **Questionnaire layout** — Questions are in a single column; auto-detected by looking for a header cell containing "question". Falls back to the column with the longest average text.
2. **Reference documents** — Plain text (UTF-8) or PDF. Other formats won't be indexed but won't crash the app.
3. **File size** — Reference docs up to ~5 MB work well; larger files will chunk slower on first upload.
4. **Single-user workflow** — Each user manages their own projects and documents; no team sharing.
5. **Groq free tier** — Rate limit ~30 req/min. Large questionnaires may hit limits; affected answers fall back to raw snippets.
6. **In-memory FAISS** — Index rebuilt from DB on every restart. Fast enough for < 1000 chunks.

---

## Trade-offs

| Decision | Why | What was traded away |
|---|---|---|
| Groq instead of OpenAI | Free, no credit card, fast inference | Slightly lower model quality; rate limits |
| Local embeddings (`sentence-transformers`) | No API costs, works offline | ~90 MB one-time download; slightly lower quality than `text-embedding-3-small` |
| SQLite instead of PostgreSQL | Zero-config, single-file DB | Not horizontally scalable; no native pgvector |
| FAISS in-memory | No external service needed | Index lost on restart (rebuilt from DB — fast enough here) |
| Session cookies instead of JWT | Simpler revocation, no client token storage | Stateful; doesn't suit stateless API clients |
| Jinja2 server-rendered instead of React | No build step, fewer moving parts | Less dynamic UX; full page reloads |

---

## What I'd Improve With More Time

**Short-term (1–2 days)**
- Persistent FAISS index file to skip rebuild on restart
- Progress bar / SSE for the generate step
- Unit tests for the parser and RAG pipeline

**Medium-term (1 week)**
- `.docx` questionnaire support
- Version history — compare original AI answer vs. edited answer
- Caching layer so identical questions across projects reuse embeddings

**Long-term**
- Fine-tuned model for the compliance/security questionnaire domain
- Multi-tenant team workspaces
- Production deployment guide (Docker + Railway / Fly.io)

---

## License

MIT — free to use as a reference or starting point.

---

**Built for the GTM Engineering Internship Assignment**  
*Demonstrating RAG-based AI systems, full-stack development, and practical ML engineering.*
