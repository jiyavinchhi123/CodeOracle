# CodeOracle

AI-powered legacy codebase analyzer and modernizer. Upload a ZIP or paste a public GitHub URL, analyze Python/Java codebases, and get explanations, dependency graphs, generated tests, modernization suggestions, and breaking-change warnings.

## Architecture

```
ZIP / GitHub URL
      ↓
  Ingestion (validate, extract safely)
      ↓
  File discovery (Python .py, Java .java)
      ↓
  Static analysis (AST / javalang)
      ↓
  Dependency graph
      ↓
  AI layer (explanations, tests, modernization, breaking changes)
      ↓
  Results API → React frontend
```

### Backend (`backend/app/`)

| Folder | Purpose |
|--------|---------|
| `api/` | FastAPI routes and dependencies |
| `models/` | Pydantic request/response schemas |
| `services/` | Ingestion, analysis pipeline, test runner, job storage |
| `analyzers/` | Python AST, Java (javalang), dependency graph |
| `ai/` | LLM provider, explainer, test generator, modernizer, breaking-change analyzer |
| `utils/` | ZIP validation, GitHub download, security helpers |

### Frontend (`frontend/`)

Single-page workflow: upload or GitHub URL → **ANALYZE** → tabbed results (Overview, Explanation, Dependencies, Tests, Modernize, Breaking Changes) with file tree and code viewer.

## Prerequisites

- Python 3.11+
- Node.js 18+
- (Optional) OpenAI-compatible LLM API key for AI-generated explanations/tests/refactoring

## Setup

### Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edit .env and set LLM_API_KEY for full AI features
```

### Frontend

```bash
cd frontend
npm install
```

## Environment Variables

Copy `backend/.env.example` to `backend/.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | LLM provider identifier | `openai` |
| `LLM_API_KEY` | API key (leave empty for heuristic mode) | — |
| `LLM_BASE_URL` | OpenAI-compatible base URL | `https://api.openai.com/v1` |
| `LLM_MODEL` | Model name | `gpt-4o-mini` |
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `8000` |
| `CORS_ORIGINS` | Allowed frontend origins | `http://localhost:5173` |
| `UPLOAD_DIR` | Job workspace directory | `./uploads` |
| `MAX_UPLOAD_SIZE_MB` | Max ZIP size | `50` |
| `GITHUB_API_BASE` | GitHub API base URL | `https://api.github.com` |
| `GITHUB_TOKEN` | Optional GitHub PAT (avoids rate limits) | — |

## Run

**Terminal 1 — Backend:**

```bash
cd backend
# IMPORTANT: use --reload-dir app so ZIP extraction does not trigger server reload
uvicorn app.main:app --reload --reload-dir app --host 0.0.0.0 --port 8000
```

Or on Windows: `run_dev.bat`

**Terminal 2 — Frontend:**

```bash
cd frontend
npm run dev
```

Open http://localhost:5173

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/analyze/zip` | Upload ZIP (`multipart/form-data`, field `file`) |
| POST | `/api/analyze/github` | Body: `{"url": "https://github.com/owner/repo"}` |
| GET | `/api/jobs/{job_id}` | Poll job status and results |
| GET | `/api/jobs/{job_id}/files/{path}` | Get file content |

## Supported Inputs

- **ZIP archives** containing `.py` and/or `.java` source files
- **Public GitHub repositories** (no private repos)

## Tests

```bash
cd backend
pytest tests/ -v
```

```bash
cd frontend
npm run build
```

## How Features Work

1. **Ingestion** — ZIPs are validated for path traversal, size limits, and file count. GitHub repos are fetched via the public API and archive download. Original code is never modified.

2. **Static analysis** — Python uses the `ast` module; Java uses `javalang`. Extracts classes, functions, imports, and line counts.

3. **Dependency graph** — Built from import statements and inheritance relationships between project files.

4. **AI explanations** — With `LLM_API_KEY` set, sends focused code snippets (not entire projects) to the LLM. Without a key, heuristic explanations are generated from static analysis metadata.

5. **Test generation** — Produces pytest (Python) or JUnit (Java) test files. Generated tests are written to `_generated_tests/` and executed in an isolated temp directory with a 30s timeout.

6. **Modernization** — Suggests refactored code stored separately under `_refactored/`. Original and refactored code are kept side-by-side for comparison.

7. **Breaking changes** — Compares original vs refactored symbols and flags parse errors.

## Security Notes

- Uploaded and AI-generated code is treated as **untrusted**
- Uploaded source code is **not executed** automatically
- Only AI-generated test files run, in a subprocess with timeout (not production-grade sandboxing)
- Path traversal in ZIPs is blocked
- Refactored files never overwrite originals

## Known Limitations

- **Heuristic mode** — Without an LLM API key, explanations/tests/modernizations use rule-based heuristics, not generative AI
- **Java test execution** — JUnit tests are generated but not fully executed unless JDK + JUnit are configured; MVP validates generation and reports skipped status
- **Job storage** — Persisted to disk under `UPLOAD_DIR` (survives server restarts)
- **Language support** — Python and Java only
- **GitHub** — Public repositories only; subject to GitHub API rate limits
- **Large projects** — AI analysis is limited to the first N files to avoid excessive token usage
- **Dev reload** — Always start with `--reload-dir app`; otherwise extracting a ZIP into `uploads/` triggers uvicorn reload and kills in-progress jobs
- **No production sandbox** — Test execution uses subprocess timeout only

## Project Structure

```
Hackorbit/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── models/
│   │   ├── services/
│   │   ├── analyzers/
│   │   ├── ai/
│   │   └── utils/
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── src/
└── README.md
```
