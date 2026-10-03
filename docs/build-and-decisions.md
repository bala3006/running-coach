# Build and Decisions Log

**Date:** 2026-10-02  
**Project:** Thunai AI · Coach Eklavya (`running-coach`)

## Goal

Build a private, local-first running coach that can use the runner's own activity and training-plan data, explain deterministic training summaries, and converse in English, Tamil, or Tanglish.

## Decisions

- **Local model only:** Ollama is the language-model provider. Chat requests go to the configured local Ollama endpoint; no hosted LLM provider is part of the initial release.
- **Read-only integrations:** Strava and Google Sheets are optional MCP integrations. Their tools fetch activity and plan data but cannot edit either service.
- **Deterministic metrics:** Python computes training metrics such as distance, duration, and pace. The model explains those values rather than calculating them from raw records.
- **Local data and credentials:** Conversation history is stored in SQLite on the machine. OAuth tokens use the operating system credential store; secrets stay out of source control.
- **Language and voice:** The app offers English, conversational Tamil, and Tanglish. The default English-plus-Tanglish response should feel warm and natural, with light Romanized Tamil when it fits. It should not append fixed Tamil dialogue or force catchphrases. The voice should remain respectful and avoid assumptions about the runner's background.
- **Model selection:** `qwen3.8:latest` produced incomplete, empty chat responses in the local setup, which surfaced as HTTP 503 from the app. `llama3.2:latest` answered successfully through the full chat and MCP path, so it is now the project default. The ignored local `.env` and checked-in `.env.example` both select it.
- **Brand:** The app is named **Thunai AI**, with **Coach Eklavya** as the coach persona.

## What Was Built

- A Python FastAPI app that serves the local chat UI, exposes chat and health endpoints, and persists chat history.
- A static HTML, CSS, and JavaScript interface with language selection, coach-warmth controls, connection settings, and chat history restoration.
- Separate stdio MCP servers for Strava and Google Sheets, connected by the app's MCP client.
- Training-summary code and response-safety handling kept outside the language model.
- OAuth handling for optional integrations, with tokens kept in the operating system credential store.
- A responsive architecture page at `docs/architecture.html`, setup instructions in `README.md`, and `scripts/run.sh` to create the virtual environment, install dependencies, initialize `.env`, and start the app.

## Run and Stop

Requirements are Python 3.11+ and Ollama. Ensure the selected model is installed:

```sh
ollama pull llama3.2:latest
```

From the repository root, start the app with:

```sh
./scripts/run.sh
```

The default address is <http://127.0.0.1:8000>. Stop the foreground server from its terminal with **Ctrl+C**.

## Verification and Remaining Setup

- The full test suite passed: **19 tests**.
- A live chat request through the updated Ollama and MCP path returned successfully with `llama3.2:latest`.
- Strava and Google Sheets still require the user's OAuth application credentials, connected accounts, and (for Sheets) a spreadsheet ID. Live provider OAuth and API flows were not verified as part of this build.

## Follow-up: Training Memory and Race Targets

**Date:** 2026-10-03

- Added explicit Strava activity sync into local SQLite, with activity summaries, available temperature, elevation gain, and descent derived from Strava altitude streams.
- Added a local SQLite FTS5 retrieval index for runs, subjective reflections, optional effort/weather fields, and race goals. Relevant memories and deterministic goal estimates are added to the local coach prompt.
- Added manual humidity and run-reflection entry. No activity coordinates are sent to a weather provider; temperature can use Strava's value when present.
- Added race goal storage and a deterministic Riegel projection from a comparable run in the last 90 days. The UI labels the result as a rough projection and shows its source and distance fit.
- Added a Training log UI for sync, reflections, conditions, and event targets.

## Follow-up: Semantic Retrieval

**Date:** 2026-10-03

- Added `nomic-embed-text:latest` through Ollama's local `/api/embed` endpoint; chat remains on `llama3.2:latest`.
- Activity, reflection, and race-goal text is embedded in batches and stored as model-versioned float32 vectors in SQLite. Updates invalidate stale vectors; pending records can be reindexed from the Training log.
- Chat query vectors are combined with SQLite FTS5 keyword results using reciprocal-rank fusion. If Ollama embeddings are unavailable, FTS5 remains the retrieval fallback.
- No vector database service or hosted embedding API is required. The embedding model must be pulled separately with `ollama pull nomic-embed-text`.

## Follow-up: Connected Analysis and Sharing

**Date:** 2026-10-03

- The Marathon sheet reader now uses effective cell fill colors; its actual light-blue color is covered by a regression test and marks completed weeks.
- Explicit marathon time-goal questions use a deterministic report from up to 90 days of Strava activity and the Marathon sheet instead of asking the model to calculate from raw rows.
- Registered read-only MCP calls are executed if the chat model emits a valid call payload as plain JSON text, preventing raw tool payloads from appearing as the answer.
- Added the app icon to the header and favicon, plus a portrait 1200×1500 architecture infographic for LinkedIn. The architecture page serves it at `/architecture/linkedin.png`.