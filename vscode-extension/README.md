# Developer Intelligence MCP — VS Code Extension
A local VS Code extension that connects to the Developer Intelligence MCP agent and lets you ask questions about your codebase directly from the sidebar.

## Features

- Dedicated Activity Bar icon and sidebar.
- Ask questions about your repository.
- Connects to the local Python agent API.
- Displays agent responses in the Developer Intelligence Output Channel.
- Shows an error message if the local API is unavailable.
- Supports the Command Palette as an alternative entry point.

## Requirements

- Python environment and project dependencies installed.
- PostgreSQL with pgvector configured.
- Gemini API key configured.
- VS Code installed.

## Run locally

1. Open the `developer-intelligence-mcp` project in VS Code.
2. Ensure the project's virtual environment and dependencies are configured.
3. Start the required services and ensure the repository is indexed.
4. Start the local agent API from the project root:

```
python -m server.agent_api
```
5. Open the `vscode-extension` folder as the extension root in a VS Code window.
6. Press `F5` to launch the Extension Development Host.
7. Open the Developer Intelligence sidebar, enter a question, and click **Ask**.
The local API runs at `http://127.0.0.1:8765`.

## Tests
Run the project's tests from the repository root:

```
python -m pytest -q
```

## Notes

- The extension requires the local Python API to be running.
- The API uses the project's configured database, embeddings, and language model.
- Keep your Gemini API key private; do not commit it to Git.
