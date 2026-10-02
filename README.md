# Thunai AI · Coach Eklavya

Thunai AI is a local-first running coach powered by Ollama, Strava, Google Sheets, and MCP. Coach Eklavya uses activity and training data you choose to connect. Chat requests go to your configured local Ollama instance; conversation history and OAuth credentials stay local.

## Start the app

Requirements: Python 3.11+ and [Ollama](https://ollama.com/). From the repository root, run:

```bash
./scripts/run.sh
```

The script creates `.venv` and `.env` if needed, installs runtime dependencies, and starts the app on <http://127.0.0.1:8000>. To use a different port, set `PORT`, for example `PORT=8010 ./scripts/run.sh`. The default model is `llama3.2:latest`; install it with `ollama pull llama3.2:latest` if needed. Set `OLLAMA_MODEL` in `.env` only if you want to use a different installed model.

Conversation history is stored in `~/.running-coach/coach.sqlite3` and can be moved by setting `RUNNING_COACH_DB`.

## Architecture

Open the [architecture page](docs/architecture.html) directly, or while the app is running visit <http://127.0.0.1:8000/architecture>.

## Coach Eklavya's voice

The default is warm English with light, natural Tanglish when it fits; the coach does not add scripted Tamil dialogue. Choose English only, Tamil, or Tanglish in the chat controls, and enable **Tamil coach warmth** for a more locally grounded voice. Tamil uses conversational Tamil; Tanglish uses Romanized Tamil. The voice does not assume a particular city, background, or running culture, and keeps training advice and units clear.

## Integrations

Strava and Google Sheets are optional. Register OAuth apps with the providers, then add their client IDs and secrets to `.env`. Set `GOOGLE_SHEET_ID` and `GOOGLE_SHEET_RANGE` to the range containing your profile or training plan. The app requests read-only scopes. OAuth tokens are stored in the operating system credential store; never put them in source control.

The Strava callback URL is `http://127.0.0.1:8000/api/integrations/strava/callback`. The Google callback URL is `http://127.0.0.1:8000/api/integrations/google/callback`. Add each exact URL to its OAuth app configuration.

## Safety and privacy

This is a training aid, not medical care. It does not diagnose injuries. Integration tools are read-only; the coach cannot change a training plan or edit your Sheet.

## Development

```bash
.venv/bin/pytest
```
