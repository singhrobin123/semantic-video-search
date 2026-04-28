# Claude Prompts — OSS Completion Roadmap

This file contains copy-pasteable prompts for another Claude session (Cascade,
Claude Code, Claude.ai, etc.) to complete the open-source readiness work on this
repo. Run them **in order** within a phase. Between phases, come back here for a
review.

---

## How to Use

1. Pick the next task below.
2. Copy the **Global Context** block once per session.
3. Paste the task prompt.
4. When the agent is done, share the diff back here for review.

Each task is designed to be **small enough to finish in one session** and
**independent enough that a failure doesn't block other tasks in the same
phase**.

---

## Global Context (prepend once per session)

```
You are working in an existing open-source repository:

  Absolute path: /Users/robin.singh/Desktop/personal-workspace/semantic-video-search
  GitHub:        https://github.com/singhrobin123/semantic-video-search
  License:       MIT (declared in README, LICENSE file may or may not exist yet)
  Stack:         Python 3.12, FastAPI, LangGraph, SQLAlchemy async, pgvector,
                 Streamlit, Docker Compose, GitHub Actions.
  Project name:  Semantic Video Search Engine
  Owner handle:  singhrobin123
  Current version (per backend/app/main.py): 2.0.0

Hard rules:
- Do NOT modify application code unless the task explicitly says so.
- Do NOT delete or weaken existing tests.
- Do NOT add comments/docstrings unless the task asks.
- Match existing code style (check neighboring files first).
- All new files must use absolute paths under the repo root.
- Prefer small, focused edits over large rewrites.
- Before claiming completion, run any verification commands listed in the task.

Tooling available on the host:
- python 3.12+, pip, pytest, docker, docker compose, make, git.
```

---

# Phase 1 — OSS Hygiene

Goal: make the repo legally complete and contributor-friendly. No code changes.

## P1-T1 — LICENSE, CHANGELOG, ROADMAP

```
TASK: Add the three baseline project docs.

Deliverables (create new files, do not overwrite if they already exist):

1. /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/LICENSE
   - Standard MIT License text.
   - Copyright line: "Copyright (c) 2024-2025 Robin Singh"
   - Year range should start 2024 and include the current year.

2. /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/CHANGELOG.md
   - Follow the "Keep a Changelog" 1.1.0 format (https://keepachangelog.com).
   - Include a header note that the project adheres to Semantic Versioning.
   - Sections: "Unreleased" (empty), then "[2.0.0] - 2025-01-01" with a
     single "Added" bullet: "Initial public release: agentic LangGraph search,
     pgvector retrieval, YouTube ingestion, Streamlit UI."
   - Add a "[1.0.0]" section with a single "Added" bullet: "Internal prototype."

3. /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/ROADMAP.md
   - Short document (~40 lines).
   - Sections: "Vision", "Near-term (next release)", "Mid-term", "Long-term",
     "Non-goals".
   - Near-term bullets: Alembic migrations, rate limiting, GHCR Docker images,
     prod compose profile, expanded docs.
   - Mid-term: reranking, multi-modal (frames+audio), citations UI polish,
     cost dashboards.
   - Long-term: self-hosted embedding models, multi-tenant, auth.
   - Non-goals: proprietary LLM lock-in, commercial-only features.

Verification:
- `ls LICENSE CHANGELOG.md ROADMAP.md` all succeed.
- `grep -c "MIT License" LICENSE` returns >= 1.
```

## P1-T2 — CONTRIBUTING, CODE_OF_CONDUCT, SECURITY

```
TASK: Add contributor-facing governance docs.

Deliverables:

1. /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/CONTRIBUTING.md
   Must cover:
   - How to set up dev env (reference existing Makefile: `make install`, `make db`,
     `make seed`, `make test`).
   - Branch naming: `feat/…`, `fix/…`, `docs/…`, `chore/…`.
   - Commit style: Conventional Commits (https://www.conventionalcommits.org).
   - PR checklist: tests added/updated, `make test` passes, `make lint` passes,
     CHANGELOG updated under "Unreleased".
   - How to run a single test: `pytest backend/tests/unit/test_chunker.py -v`.
   - Link to CODE_OF_CONDUCT.md and SECURITY.md.
   - Note that the project targets Python 3.12+.

2. /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/CODE_OF_CONDUCT.md
   - Verbatim Contributor Covenant v2.1 (https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
   - Replace the contact placeholder with: "Please open a private security
     advisory on GitHub (see SECURITY.md) for serious violations."

3. /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/SECURITY.md
   Must include:
   - "Supported Versions" table: 2.x ✅, < 2.0 ❌.
   - Private disclosure: GitHub Security Advisories
     (https://github.com/singhrobin123/semantic-video-search/security/advisories/new).
   - Response SLA: acknowledgement within 72 hours, fix target 30 days for
     high-severity.
   - Scope: app code, default Docker images, dependency pins. Out of scope:
     third-party LLM providers, user-supplied transcripts.

Verification:
- All three files exist.
- No TODO placeholders remain.
- `grep -i "contributor covenant" CODE_OF_CONDUCT.md` succeeds.
```

## P1-T3 — GitHub Templates, CODEOWNERS, Dependabot

```
TASK: Add GitHub automation metadata.

Deliverables (create if missing, don't overwrite):

1. /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/.github/ISSUE_TEMPLATE/bug_report.yml
   - GitHub issue form (YAML schema).
   - Fields: Summary, Steps to reproduce, Expected, Actual, Environment
     (OS, Python version, commit SHA), Logs.
   - Labels: ["bug", "triage"].

2. /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/.github/ISSUE_TEMPLATE/feature_request.yml
   - Fields: Problem, Proposed solution, Alternatives considered.
   - Labels: ["enhancement", "triage"].

3. /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/.github/ISSUE_TEMPLATE/question.yml
   - Fields: Question, What you have tried.
   - Labels: ["question"].

4. /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/.github/ISSUE_TEMPLATE/config.yml
   - blank_issues_enabled: false
   - contact_links: one entry pointing to GitHub Discussions (leave URL as
     https://github.com/singhrobin123/semantic-video-search/discussions).

5. /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/.github/pull_request_template.md
   Sections: Summary, Related issue, Type of change (checkboxes: bug/feat/
   docs/chore/refactor/test), Checklist (tests pass, lint passes, CHANGELOG
   updated, docs updated if applicable), Screenshots (if UI).

6. /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/.github/CODEOWNERS
   One line: `* @singhrobin123`

7. /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/.github/dependabot.yml
   Three update ecosystems, weekly schedule, open-pull-requests-limit: 5,
   commit-message prefix "chore(deps):":
   - pip in /backend
   - docker in /backend
   - github-actions in /

Verification:
- `ls .github/ISSUE_TEMPLATE/*.yml .github/pull_request_template.md .github/CODEOWNERS .github/dependabot.yml`
- `python -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/**/*.yml', recursive=True)]"` must not raise.
```

---

# Phase 2 — Code Quality Baseline

Goal: formal project metadata, enforced style, stronger CI.

## P2-T1 — pyproject.toml + tool configuration

```
TASK: Introduce a pyproject.toml for the backend with tool configs and
optional dependency groups. Do NOT delete requirements.txt (keep for Docker
layer caching).

Deliverables:

1. Create /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/backend/pyproject.toml
   with the following:
   - [project]: name="semantic-video-search", version="2.0.0", requires-python=">=3.12",
     description matching the FastAPI title, readme points to "../README.md",
     license = {text = "MIT"}, authors = [{name = "Robin Singh"}].
   - [project.dependencies]: mirror backend/requirements.txt runtime deps
     (fastapi, uvicorn[standard], pydantic, pydantic-settings, sqlalchemy[asyncio],
     asyncpg, pgvector, langchain, langchain-openai, langgraph, openai,
     youtube-transcript-api, yt-dlp, structlog, python-dotenv, httpx) with
     the same lower-bound pins.
   - [project.optional-dependencies]:
       - dev = [pytest, pytest-asyncio, pytest-cov, ruff, black, mypy,
                pre-commit, pip-audit]
       - anthropic = [langchain-anthropic>=0.3.0]
   - [tool.ruff]: line-length=100, target-version="py312",
     extend-exclude=[".venv","venv","build","dist"], select for rules
     ["E","F","W","I","UP","B","SIM","RUF"], ignore=["E501"] (let formatter
     handle length).
   - [tool.ruff.format]: quote-style="double".
   - [tool.black]: line-length=100, target-version=["py312"].
   - [tool.mypy]: python_version="3.12", ignore_missing_imports=true,
     warn_unused_ignores=true, plugins=["pydantic.mypy"], packages=["app"].
   - [tool.pytest.ini_options]: testpaths=["tests"], asyncio_mode="auto",
     addopts="-ra --strict-markers".
   - [tool.coverage.run]: source=["app"], branch=true.
   - [tool.coverage.report]: show_missing=true, skip_empty=true,
     exclude_lines default list + "if __name__ == .__main__.:".

2. Update /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/Makefile:
   - `lint` → `cd backend && python -m ruff check app tests && python -m mypy app`
   - Add `format` → `cd backend && python -m ruff check --fix app tests && python -m black app tests`
   - Add `format-check` → `cd backend && python -m black --check app tests && python -m ruff check app tests`
   - Add `precommit` → `pre-commit run --all-files`
   - Keep all existing targets untouched.

Constraints:
- Do NOT run formatters in this task (that's P2-T2).
- Do NOT remove requirements.txt.

Verification:
- `python -c "import tomllib,pathlib; tomllib.loads(pathlib.Path('backend/pyproject.toml').read_text())"` succeeds.
- `make help` still prints the full target list with the new entries.
```

## P2-T2 — Pre-commit + one-time formatter pass

```
TASK: Add a pre-commit config and run the formatter once across the codebase.

Prerequisite: P2-T1 merged.

Deliverables:

1. /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/.pre-commit-config.yaml
   Hooks:
   - pre-commit-hooks: trailing-whitespace, end-of-file-fixer, check-yaml,
     check-merge-conflict, check-added-large-files (>500kb).
   - ruff-pre-commit: ruff (with --fix) and ruff-format, pinned versions.
   - mirrors-mypy: mypy with additional_dependencies matching pyproject
     (pydantic, types-requests).
   Use a `default_stages: [pre-commit]` and pin versions.

2. Run the formatters once:
   - `cd backend && pip install -e ".[dev]"`
   - `cd backend && python -m ruff check --fix app tests`
   - `cd backend && python -m black app tests`
   - `cd backend && python -m ruff format app tests` (or black — pick one consistently)

3. If mypy reports issues, add the MINIMUM `# type: ignore[...]` comments to
   keep mypy green. Prefer adding stubs in pyproject.toml overrides over
   code-level ignores.

Constraints:
- Do NOT change any application logic; only formatting and ignores.
- Commit the formatter changes as a SEPARATE commit with message
  "chore: apply ruff + black formatting".

Verification:
- `cd backend && python -m pytest` still passes all 36 tests.
- `cd backend && python -m ruff check app tests` exits 0.
- `cd backend && python -m black --check app tests` exits 0.
- `pre-commit run --all-files` exits 0.
```

## P2-T3 — Lint, security, and CodeQL workflows

```
TASK: Extend CI with quality and security jobs. Do not modify the existing
test job in ci.yml (leave tests passing).

Deliverables:

1. /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/.github/workflows/lint.yml
   Triggers: push to main, pull_request.
   One job "lint" on ubuntu-latest with Python 3.12:
     - Install `backend/[dev]` optional deps.
     - Run `python -m ruff check backend/app backend/tests`.
     - Run `python -m black --check backend/app backend/tests`.
     - Run `python -m mypy backend/app`.

2. /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/.github/workflows/security.yml
   Triggers: push to main, pull_request, schedule weekly (Monday 06:00 UTC).
   Two jobs:
     - "pip-audit": install requirements, run `pip-audit -r backend/requirements.txt --strict`.
     - "trivy": scan the backend Dockerfile (`aquasecurity/trivy-action@master`,
       scan-type: fs, severity: CRITICAL,HIGH, exit-code: 1).

3. /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/.github/workflows/codeql.yml
   Use the standard GitHub CodeQL v3 workflow for Python, weekly schedule.

Constraints:
- All new workflows must pass (or be clearly marked `continue-on-error: true`
  only where a CVE is known to be false-positive).
- Do not bump the existing test workflow's actions.

Verification:
- `python -c "import yaml; [yaml.safe_load(open(f)) for f in ['.github/workflows/lint.yml','.github/workflows/security.yml','.github/workflows/codeql.yml']]"` succeeds.
- After push, all three workflows appear on the Actions tab.
```

---

# Phase 3 — Test & Release Maturity

Goal: close coverage gaps, automate releases, introduce migrations.

## P3-T1 — Missing unit tests

```
TASK: Add unit tests for modules that currently have zero direct coverage.
Mock all external services (OpenAI, DB connections). Follow the patterns in
backend/tests/unit/test_tools.py and test_chunker.py.

Read first:
- backend/app/db/repository.py
- backend/app/ingestion/embedder.py
- backend/app/ingestion/pipeline.py
- backend/app/llm/provider.py
- backend/app/api/middleware.py
- backend/app/config.py
- backend/tests/conftest.py

Deliverables (each is a new file under backend/tests/unit/):

1. test_repository.py  — mock AsyncSession via sqlalchemy-mock or an in-memory
   SQLite-with-vector-stub strategy. At minimum test: upsert_clip idempotency,
   bulk_insert_chunks ordering, list_clips, delete_clip cascade, and the KNN
   query builder (ensure the SQL contains "<=>" and LIMIT clauses).

2. test_embedder.py — mock openai.embeddings.create. Assert: batches of 512,
   preserves order, passes the embedding model name from settings.

3. test_pipeline.py — monkeypatch transcriber, chunker, embedder, repository.
   Assert end-to-end ingest_youtube_video returns correct IngestionResult and
   calls each stage exactly once.

4. test_provider.py — assert get_llm() returns an OpenAI client when
   LLM_PROVIDER=openai and an Anthropic one when LLM_PROVIDER=anthropic.
   Use `monkeypatch.setenv` + `get_settings.cache_clear()`.

5. test_middleware.py — use starlette's TestClient against a mini FastAPI app
   with only RequestTracingMiddleware installed. Assert:
     - X-Request-ID header is echoed when provided, generated when absent.
     - X-Response-Time-Ms is a positive integer.

6. test_config.py — cover the CORS JSON parser, the embedding_dimensions
   property for all three mapped models + a fallback, and is_production.

Constraints:
- No network calls, no real DB.
- Each file should add 4-8 tests. Keep file <150 lines.
- Preserve the existing 36-test green bar; total should be >= 60 after.

Verification:
- `cd backend && python -m pytest tests/unit -v` exits 0.
- `cd backend && python -m pytest tests/ --cov=app` prints >= 70% coverage.
```

## P3-T2 — End-to-end integration test

```
TASK: Add a real ingest→search integration test that runs against the
pgvector CI service.

Read first:
- backend/tests/integration/test_api_routes.py
- .github/workflows/ci.yml  (note: DATABASE_URL env var is already set)

Deliverable:

/Users/robin.singh/Desktop/personal-workspace/semantic-video-search/backend/tests/integration/test_ingest_search_e2e.py

Flow:
1. Use the httpx.AsyncClient fixture (same pattern as test_api_routes.py).
2. POST /api/v1/ingest/manual with a small handcrafted transcript (3-5
   entries about "connection pool exhaustion").
3. Assert 200, capture clip_id, assert chunks_stored > 0.
4. Monkeypatch the agent's tool calls OR mock `build_graph` so the search
   step does NOT hit a real LLM. Instead assert that:
     - GET /api/v1/library now includes the new clip.
     - DELETE /api/v1/library/{clip_id} returns 200.
     - A second DELETE returns 404.

Constraints:
- Must not require OPENAI_API_KEY to be real (use a stub embedder via
  monkeypatch on app.ingestion.embedder.embed_chunks to return zero-vectors
  of correct dim).
- Mark with @pytest.mark.integration.

Verification:
- `cd backend && DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/vectordb python -m pytest tests/integration -v`
  passes locally against a running pgvector container.
```

## P3-T3 — Codecov + Python 3.13 matrix

```
TASK: Extend the existing CI workflow.

Edit: /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/.github/workflows/ci.yml

Changes:
1. Convert the test job to a matrix on python-version: ["3.12", "3.13"].
2. After the coverage step, add a Codecov upload using
   codecov/codecov-action@v4 with file: backend/coverage.xml. Make it
   `if: matrix.python-version == '3.12'` to avoid double uploads.
3. Keep existing steps and env vars intact.

Also update the top of README.md to add a Codecov badge after the Tests badge:
https://codecov.io/gh/singhrobin123/semantic-video-search/branch/main/graph/badge.svg

Constraints:
- Do not break the existing run on 3.12.
- Both matrix cells must pass green.

Verification:
- YAML parses: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`.
- CI passes on both 3.12 and 3.13.
```

## P3-T4 — Release workflow (GHCR + GitHub Release)

```
TASK: Add automated Docker image publishing and GitHub Release creation
on semver tags.

Deliverable:

/Users/robin.singh/Desktop/personal-workspace/semantic-video-search/.github/workflows/release.yml

Triggers: push tags matching `v*.*.*`.

Two jobs:

1. "docker" — builds and publishes backend + frontend images to GHCR.
   Steps:
   - actions/checkout@v4
   - docker/setup-qemu-action@v3
   - docker/setup-buildx-action@v3
   - docker/login-action@v3 (registry: ghcr.io, username: github.actor,
     password: secrets.GITHUB_TOKEN)
   - For each of backend, frontend: docker/build-push-action@v6 with
     tags ghcr.io/singhrobin123/semantic-video-search-<svc>:${{ github.ref_name }}
     and :latest. Use cache-from/to with type=gha.
   - Permissions: contents: read, packages: write.

2. "release" — creates a GitHub Release.
   - Needs: docker.
   - Uses softprops/action-gh-release@v2.
   - body_path: CHANGELOG.md (or extracts the matching section — prefer
     a small Python script that prints the section for the tag and pipes
     into body).
   - fail_on_unmatched_files: false.

Also update README.md's "Quick Start" with a new "Option C: Pull Prebuilt
Images" block showing `docker pull ghcr.io/singhrobin123/…` commands.

Verification:
- `python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))"` succeeds.
- Dry-run tag locally: `git tag v2.0.1-test && git push --tags` (user will run, not the agent).
```

## P3-T5 — Alembic migrations

```
TASK: Replace the ad-hoc create_all bootstrap with Alembic so schema changes
are versioned.

Read first:
- backend/app/db/models.py
- backend/app/db/session.py (note: init_db currently runs metadata.create_all)

Deliverables:

1. Add alembic + alembic-utils to pyproject.toml dev group AND runtime (needed
   at container start).

2. Initialize Alembic under backend/alembic/ with async template:
   - backend/alembic.ini
   - backend/alembic/env.py   (async engine, loads DATABASE_URL from settings,
     imports Base metadata from app.db.models)
   - backend/alembic/script.py.mako  (standard)
   - backend/alembic/versions/0001_initial.py  (autogenerated baseline +
     CREATE EXTENSION IF NOT EXISTS vector and the HNSW index DDL).

3. Change backend/app/db/session.py `init_db` to:
   - On startup, run `alembic upgrade head` programmatically
     (via alembic.config.Config + command.upgrade).
   - Remove the metadata.create_all call.

4. Update Makefile:
   - `make migrate` → `cd backend && alembic upgrade head`
   - `make migration` → `cd backend && alembic revision --autogenerate -m "$(m)"`

5. Update CI (ci.yml) to run `cd backend && alembic upgrade head` BEFORE
   tests in the job that needs a schema.

Constraints:
- The initial migration must be idempotent (pgvector extension + HNSW index
  creation uses IF NOT EXISTS).
- All existing tests must still pass.

Verification:
- `cd backend && alembic upgrade head` against a fresh pgvector container
  succeeds twice (second run is a no-op).
- `make test` passes.
```

---

# Phase 4 — Production Polish

Goal: things a serious adopter will notice.

## P4-T1 — Prod compose profile + hardened backend Dockerfile

```
TASK: Ship a production compose file and harden the backend image.

Deliverables:

1. Edit /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/backend/Dockerfile:
   - Multi-stage: builder installs wheels, runtime copies them.
   - Create a non-root user `app` (UID 1000) and USER app before CMD.
   - Add HEALTHCHECK CMD curl -fsS http://127.0.0.1:8000/health || exit 1
     (install curl in runtime stage).
   - Drop --reload from CMD.

2. Edit the existing /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/docker-compose.yml:
   - Remove the `version: "3.8"` line (Compose v2 warns).
   - Keep it as the DEV compose file (bind mounts + --reload OK here).

3. Create /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/docker-compose.prod.yml:
   - No bind mounts.
   - No --reload.
   - Restart policy: unless-stopped for all services.
   - Backend and frontend pulled from ghcr.io (allow override via env).
   - pgvector volume is named and backed up-able.
   - Optional: add a traefik/caddy reverse proxy stub, commented out.

4. Update Makefile:
   - `make up`          → dev compose (unchanged).
   - `make up-prod`     → `docker compose -f docker-compose.prod.yml up -d`.
   - `make down-prod`   → `docker compose -f docker-compose.prod.yml down`.

Verification:
- `docker compose -f docker-compose.prod.yml config` exits 0 (validates schema).
- `docker build -t svs-backend backend/` succeeds.
- The built image's user is `app`: `docker run --rm --entrypoint whoami svs-backend`.
```

## P4-T2 — Fail-fast config + frontend API_BASE env

```
TASK: Make two small correctness fixes.

Read first:
- backend/app/config.py
- backend/app/main.py
- frontend/app.py:24

Changes:

1. In backend/app/config.py:
   - Add a model_validator(mode="after") that raises ValueError at startup if
     llm_provider == LLMProvider.OPENAI and openai_api_key is empty, OR
     llm_provider == LLMProvider.ANTHROPIC and anthropic_api_key is empty.
   - Update backend/tests/unit/test_config.py (if present) with a test that
     constructing Settings with an empty key for the selected provider raises.

2. In frontend/app.py:
   - Replace the hardcoded `API_BASE = "http://127.0.0.1:8000/api/v1"` with:
       API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")
   - Add `import os` at the top.
   - Update docker-compose.yml frontend service: add
       environment:
         API_BASE_URL: http://backend:8000/api/v1
   - Do the same in docker-compose.prod.yml.

3. Update .env.example to document API_BASE_URL.

Verification:
- `cd backend && OPENAI_API_KEY='' LLM_PROVIDER=openai python -c "from app.config import get_settings; get_settings()"` raises.
- `cd backend && OPENAI_API_KEY=x LLM_PROVIDER=openai python -c "from app.config import get_settings; get_settings()"` succeeds.
- Compose config still validates.
```

## P4-T3 — Rate limiting

```
TASK: Add in-process rate limiting on cost-amplifying endpoints.

Read first:
- backend/app/api/routes.py
- backend/app/main.py

Changes:

1. Add `slowapi>=0.1.9` to backend dependencies (pyproject.toml AND requirements.txt).

2. Create backend/app/api/rate_limit.py with:
   - A slowapi Limiter keyed on client IP (get_remote_address).
   - Exported `limiter` singleton.

3. In backend/app/main.py:
   - Attach limiter to app.state.
   - Register slowapi's _rate_limit_exceeded_handler.
   - Add SlowAPIMiddleware.

4. In backend/app/api/routes.py:
   - Decorate POST /search with @limiter.limit("20/minute").
   - Decorate POST /ingest/youtube with @limiter.limit("5/minute").
   - Decorate POST /ingest/manual with @limiter.limit("10/minute").
   - Ensure 429 responses still go through the APIEnvelope shape (provide
     a custom handler that wraps slowapi's default).

5. Add backend/tests/unit/test_rate_limit.py: submit 25 /search requests via
   TestClient and assert at least one 429. Reset the limiter between tests.

6. Document the defaults in .env.example as comments (values are not yet
   configurable via env — note this as a TODO).

Verification:
- `make test` passes.
- Manual: 21st request to /search within a minute returns 429 with the envelope.
```

## P4-T4 — Expanded docs + examples/

```
TASK: Split the monolithic README into discoverable docs and add runnable
examples.

Deliverables:

1. /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/docs/development.md
   - Environment setup, running tests, debugging tips, repo layout.
   - Link back from README's "Quick Start — Option B".

2. /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/docs/deployment.md
   - Dev vs prod compose differences.
   - Env var reference (authoritative — README links here).
   - Secrets management guidance (GHCR pull tokens, OpenAI key rotation).

3. /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/docs/troubleshooting.md
   - Common errors: "Cannot reach backend", missing API key, pgvector
     extension missing, youtube-transcript-api 429s.

4. /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/examples/
   - curl.sh:     all endpoints as bash snippets.
   - client.py:   a ~40-line Python client using httpx (sync) that ingests
                  a URL and runs a search.
   - README.md:   explains how to run each example.

5. In the main README, REPLACE the long "Configuration" table with a link to
   docs/deployment.md#configuration. Keep the top-level architecture diagrams.

Constraints:
- Do NOT duplicate content — README points to docs/, docs/ are canonical.
- All new docs must link back to the main README.

Verification:
- `find docs examples -type f -name '*.md'` lists the new files.
- `python examples/client.py --help` runs (requires the backend, but
  --help should not).
```

## P4-T5 — Visual polish

```
TASK: Add the missing visual assets and tidy README.

Deliverables:

1. /Users/robin.singh/Desktop/personal-workspace/semantic-video-search/docs/assets/
   - screenshot-search.png  (placeholder 1280x720 if user hasn't provided —
     fall back to generating a blank PNG with a TODO label; the user will
     replace it).
   - screenshot-ingest.png  (same treatment).
   - demo.gif               (placeholder).

2. Update README.md:
   - Replace the text-based "Ingest → Ask → Cite" table near the top with
     `![…](docs/assets/demo.gif)` wrapped in a centered <div>.
   - Add a "Screenshots" section under "How It Works" with the two PNGs.
   - Add a Codecov badge (after Phase 3 P3-T3 is done) and a Docker Pulls
     badge for GHCR (after P3-T4).
   - Add a "Live Demo" line near the top — link TBD (leave `<!-- TODO: add
     deployed URL -->`).

3. Ensure README's ToC still matches (regenerate if needed).

Constraints:
- Do NOT invent screenshots. Placeholders with a clear "Replace me" text
  are fine.
- Keep README under 900 lines total after the split from P4-T4.

Verification:
- `grep -c "docs/assets" README.md` >= 3.
- `ls docs/assets/*.png` returns 2 files.
```

---

# Review Protocol

After each phase, run:

```bash
cd /Users/robin.singh/Desktop/personal-workspace/semantic-video-search
git status
git diff --stat
make test
make lint        # after Phase 2
```

Then share the diff + output with me and I'll:
1. Verify deliverables match the prompt.
2. Run the verification commands.
3. Flag regressions (broken tests, style drift, missing files).
4. Produce a go/no-go for the next phase.
