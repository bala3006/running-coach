# Project guidance

- Keep the coach local-first. Ollama is the only language-model provider.
- Integrations must be read-only in the initial release.
- Use the official MCP Python SDK (`mcp` 2.x) for MCP servers and clients: https://github.com/modelcontextprotocol/python-sdk
- MCP server stdio output is reserved for protocol messages. Log to stderr, never stdout.
- Keep training metrics deterministic and tested; do not ask the language model to calculate them.
- Coach language options include English, natural Tamil, and conversational Tanglish. Avoid stereotypes and preserve the user's requested language.
- Store OAuth tokens in the operating system credential store; never commit secrets.
