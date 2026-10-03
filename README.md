# Thunai AI · Coach Eklavya

Thunai AI is a local-first running coach powered by Ollama, Strava, Google Sheets, and MCP. Coach Eklavya uses activity and training data you choose to connect. Chat requests go to your configured local Ollama instance; conversation history and OAuth credentials stay local.

## Start the app

Requirements: Python 3.11+ and [Ollama](https://ollama.com/). From the repository root, run:

```bash
./scripts/run.sh
```

The script creates `.venv` and `.env` if needed, installs runtime dependencies, and starts the app on <http://127.0.0.1:8000>. To use a different port, set `PORT`, for example `PORT=8010 ./scripts/run.sh`. Install the local chat and embedding models:

```sh
ollama pull llama3.2:latest
ollama pull nomic-embed-text
```

The defaults are `OLLAMA_MODEL=llama3.2:latest` and `OLLAMA_EMBED_MODEL=nomic-embed-text:latest`. Both run through the local Ollama service; choose other installed models in `.env` if needed.

Conversation history is stored in `~/.running-coach/coach.sqlite3` and can be moved by setting `RUNNING_COACH_DB`.

## Architecture

Open the [architecture page](docs/architecture.html) directly, or while the app is running visit <http://127.0.0.1:8000/architecture>.

For a LinkedIn-ready overview, see the [architecture infographic](docs/thunai-ai-linkedin-architecture.png).
The app uses the [Thunai AI icon](docs/thunai-ai-strava-icon.png) in its header and favicon; the architecture page also serves the infographic at <http://127.0.0.1:8000/architecture/linkedin.png>.

## Coach Eklavya's voice

The default is warm English with light, natural Tanglish when it fits; the coach does not add scripted Tamil dialogue. Choose English only, Tamil, or Tanglish in the chat controls, and enable **Tamil coach warmth** for a more locally grounded voice. Tamil uses conversational Tamil; Tanglish uses Romanized Tamil. The voice does not assume a particular city, background, or running culture, and keeps training advice and units clear.

## Training memory and race targets

Open **Training log** in the app to sync recent Strava runs into the local SQLite database, add a run reflection, and save an upcoming race target. Activity details include distance, moving time, heart rate, elevation gain, available temperature, and descent derived from Strava altitude streams. Reflections can add effort, how the run felt, notes, temperature, and humidity. Humidity is manual because Strava does not provide a reliable activity field for it; the app does not send route coordinates to a weather service.

Saved activities, reflections, and race goals use hybrid local retrieval: SQLite FTS5 finds exact terms while Ollama embeddings find semantically related records. Vectors are stored in SQLite, and chat combines both result rankings before adding the relevant context to the local coach prompt. If the embedding model is unavailable, keyword retrieval continues to work. Race goals receive a deterministic Riegel projection using a comparable run from the last 90 days. The result shows whether the target is within the rough projection or is a stretch, along with its source run and distance fit. It is an estimate, not a guarantee; it does not replace a coach's or clinician's judgment.

## Integrations

Strava and Google Sheets are optional. Register OAuth apps with the providers, then add their client IDs and secrets to `.env`. Set `GOOGLE_SHEET_ID` and `GOOGLE_SHEET_RANGE` to the range containing your profile or training plan. The Sheets reader also reads cell fill formatting: any light-blue cell marks that row as completed in the returned training data. It uses the Sheets API read-only scope; OAuth tokens are stored in the operating system credential store and never belong in source control.

The Strava callback URL is `http://127.0.0.1:8000/api/integrations/strava/callback`. The Google callback URL is `http://127.0.0.1:8000/api/integrations/google/callback`. Add each exact URL to its OAuth app configuration.

## Safety and privacy

This is a training aid, not medical care. It does not diagnose injuries. Integration tools are read-only; the coach cannot change a training plan or edit your Sheet.

## Development

```bash
.venv/bin/pytest
```
