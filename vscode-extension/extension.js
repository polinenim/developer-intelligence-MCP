
const vscode = require('vscode');
const { randomUUID } = require('crypto');

const API_ENDPOINT = 'http://127.0.0.1:8765/ask';
const MAX_QUESTION_LENGTH = 4000;
const REQUEST_TIMEOUT_MS = 30_000;
const conversationIds = new Map();

function createRequestBody(question) {
  const workspaceFolders = vscode.workspace.workspaceFolders;
  const repositoryRoot =
    Array.isArray(workspaceFolders) && workspaceFolders.length > 0
      ? workspaceFolders[0].uri.fsPath
      : null;

  const body = { question };
  if (repositoryRoot) body.repository_root = repositoryRoot;
  const conversationKey = repositoryRoot || 'no-workspace';
  if (!conversationIds.has(conversationKey)) {
    conversationIds.set(conversationKey, randomUUID());
  }
  body.conversation_id = conversationIds.get(conversationKey);
  return body;
}

function formatAnswer(answer) {
  if (!answer) {
    return 'No answer returned.';
  }

  return answer
    .trim()
    .replace(/^Based on the repository.*?:\s*/i, '')
    .replace(/\n{3,}/g, '\n\n');
}

function createChatPanelHtml(nonce) {
  return `<!DOCTYPE html>
  <html lang="en">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${nonce}';">
    <title>Developer Intelligence Chat</title>
    <style>
      body {
        color: var(--vscode-foreground);
        background: var(--vscode-editor-background);
        font-family: var(--vscode-font-family);
        font-size: var(--vscode-font-size);
        margin: 0;
        padding: 20px;
      }
      main { max-width: 900px; margin: 0 auto; }
      h1 { font-size: 1.25rem; margin: 0 0 16px; }
      #messages {
        display: flex;
        flex-direction: column;
        gap: 12px;
        min-height: 180px;
        max-height: calc(100vh - 220px);
        overflow-y: auto;
        padding: 4px 2px 16px;
      }
      .message {
        max-width: 85%;
        border-radius: 8px;
        line-height: 1.5;
        overflow-wrap: anywhere;
        padding: 10px 12px;
        white-space: pre-wrap;
      }
      .user {
        align-self: flex-end;
        background: var(--vscode-button-background);
        color: var(--vscode-button-foreground);
      }
      .assistant {
        align-self: flex-start;
        background: var(--vscode-textBlockQuote-background);
        border: 1px solid var(--vscode-panel-border);
      }
      form { display: flex; flex-direction: column; gap: 8px; }
      textarea {
        box-sizing: border-box;
        min-height: 78px;
        resize: vertical;
        width: 100%;
        color: var(--vscode-input-foreground);
        background: var(--vscode-input-background);
        border: 1px solid var(--vscode-input-border, transparent);
        font: inherit;
        padding: 10px;
      }
      button {
        align-self: flex-end;
        background: var(--vscode-button-background);
        border: 0;
        color: var(--vscode-button-foreground);
        cursor: pointer;
        font: inherit;
        padding: 7px 16px;
      }
      button:hover { background: var(--vscode-button-hoverBackground); }
      button:disabled { cursor: default; opacity: 0.6; }
      #status { min-height: 1.4em; margin: 0 0 8px; }
      #status.error { color: var(--vscode-errorForeground); }
    </style>
  </head>
  <body>
    <main>
      <h1>Developer Intelligence</h1>
      <div id="messages" role="log" aria-live="polite"></div>
      <p id="status" aria-live="polite"></p>
      <form id="chat-form">
        <textarea id="question" maxlength="${MAX_QUESTION_LENGTH}" placeholder="Ask a question about this repository..." aria-label="Your question"></textarea>
        <button id="send" type="submit">Send</button>
      </form>
    </main>
    <script nonce="${nonce}">
      const vscode = acquireVsCodeApi();
      const form = document.getElementById('chat-form');
      const input = document.getElementById('question');
      const sendButton = document.getElementById('send');
      const messages = document.getElementById('messages');
      const status = document.getElementById('status');
      let isProcessing = false;

      function addMessage(role, text) {
        const message = document.createElement('div');
        message.className = 'message ' + role;
        message.textContent = text;
        messages.appendChild(message);
        messages.scrollTop = messages.scrollHeight;
      }

      function setProcessing(processing) {
        isProcessing = processing;
        input.disabled = processing;
        sendButton.disabled = processing;
        status.classList.remove('error');
        status.textContent = processing ? 'Thinking...' : '';
      }

      form.addEventListener('submit', (event) => {
        event.preventDefault();
        if (isProcessing) return;

        const question = input.value.trim();
        if (!question) {
          status.classList.add('error');
          status.textContent = 'Enter a question before sending.';
          return;
        }
        if (question.length > ${MAX_QUESTION_LENGTH}) {
          status.classList.add('error');
          status.textContent = 'Question is too long. Use ${MAX_QUESTION_LENGTH} characters or fewer.';
          return;
        }

        addMessage('user', question);
        input.value = '';
        setProcessing(true);
        vscode.postMessage({ type: 'ask', question });
      });

      window.addEventListener('message', (event) => {
        const message = event.data;
        if (!message || typeof message !== 'object' || Array.isArray(message)) return;

        if (message.type === 'answer' && typeof message.answer === 'string') {
          addMessage('assistant', message.answer);
          setProcessing(false);
        } else if (message.type === 'error' && typeof message.message === 'string') {
          setProcessing(false);
          status.classList.add('error');
          status.textContent = message.message;
        }
      });
    </script>
  </body>
  </html>`;
}

function activate(context) {
  console.log('[Developer Intelligence] Extension activated');

  const output = vscode.window.createOutputChannel(
    'Developer Intelligence'
  );
  let chatPanel;

  async function askAgent(question) {
    const normalizedQuestion =
      typeof question === 'string' ? question.trim() : '';

    if (!normalizedQuestion) {
      vscode.window.showWarningMessage('Enter a question before asking the agent.');
      return;
    }
    if (normalizedQuestion.length > MAX_QUESTION_LENGTH) {
      vscode.window.showWarningMessage(
        `Question is too long. Use ${MAX_QUESTION_LENGTH.toLocaleString()} characters or fewer.`
      );
      return;
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    try {
      // Determine the active workspace folder (if any) and include it
      // so the backend can operate on the opened repository. Handle the
      // case where no folder is open gracefully.
      const body = createRequestBody(normalizedQuestion);

      const resp = await fetch(API_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!resp.ok) {
        let errorMessage = `Request failed (${resp.status})`;
        const responseText = (await resp.text()).trim();
        if (responseText) {
          try {
            const errorJson = JSON.parse(responseText);
            if (typeof errorJson.error === 'string') {
              errorMessage = errorJson.error;
            }
          } catch {
            errorMessage = responseText;
          }
        }
        vscode.window.showErrorMessage(`Agent error: ${errorMessage}`);
        return;
      }

      let json;
      try {
        json = JSON.parse(await resp.text());
      } catch {
        vscode.window.showErrorMessage(
          'Agent API returned an invalid response.'
        );
        return;
      }
      const answer = formatAnswer(
        json.answer || 'No answer returned.'
      );

      output.appendLine(`You: ${normalizedQuestion}`);
      output.appendLine(`Agent: ${answer}`);
      output.appendLine('');

      output.show(true);
    } catch (err) {
      if (err && err.name === 'AbortError') {
        vscode.window.showErrorMessage(
          'Agent request timed out. Check that the local agent API is running.'
        );
        return;
      }
      vscode.window.showErrorMessage(
        'Could not contact local agent API: ' + String(err)
      );
    } finally {
      clearTimeout(timeout);
    }
  }

  const openChatPanel = vscode.commands.registerCommand(
    'developerIntelligence.openChatPanel',
    () => {
      if (chatPanel) {
        chatPanel.reveal(vscode.ViewColumn.Beside);
        return;
      }

      const panel = vscode.window.createWebviewPanel(
        'developerIntelligence.chatPanel',
        'Developer Intelligence Chat',
        vscode.ViewColumn.Beside,
        {
          enableScripts: true,
          localResourceRoots: [],
        }
      );
      chatPanel = panel;
      let disposed = false;
      let isProcessing = false;
      let activeController;

      panel.webview.html = createChatPanelHtml(randomUUID().replace(/-/g, ''));

      const messageSubscription = panel.webview.onDidReceiveMessage(
        async (message) => {
          if (
            !message ||
            typeof message !== 'object' ||
            Array.isArray(message) ||
            message.type !== 'ask' ||
            typeof message.question !== 'string'
          ) {
            panel.webview.postMessage({
              type: 'error',
              message: 'Invalid chat message.',
            });
            return;
          }

          const question = message.question.trim();
          if (!question) {
            panel.webview.postMessage({
              type: 'error',
              message: 'Enter a question before sending.',
            });
            return;
          }
          if (question.length > MAX_QUESTION_LENGTH) {
            panel.webview.postMessage({
              type: 'error',
              message: `Question is too long. Use ${MAX_QUESTION_LENGTH.toLocaleString()} characters or fewer.`,
            });
            return;
          }
          if (isProcessing) return;

          isProcessing = true;
          const controller = new AbortController();
          activeController = controller;
          const timeout = setTimeout(
            () => controller.abort(),
            REQUEST_TIMEOUT_MS
          );

          try {
            const response = await fetch(API_ENDPOINT, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(createRequestBody(question)),
              signal: controller.signal,
            });
            const responseText = (await response.text()).trim();
            let result;
            try {
              result = responseText ? JSON.parse(responseText) : null;
            } catch {
              result = null;
            }

            if (!response.ok) {
              const errorMessage =
                result && typeof result.error === 'string'
                  ? result.error
                  : responseText || `Request failed (${response.status})`;
              const error = new Error(`Agent API error: ${errorMessage}`);
              error.name = 'AgentApiError';
              throw error;
            }
            if (!result || typeof result.answer !== 'string') {
              const error = new Error('Agent API returned an invalid response.');
              error.name = 'AgentResponseError';
              throw error;
            }

            if (!disposed) {
              panel.webview.postMessage({
                type: 'answer',
                answer: formatAnswer(result.answer),
              });
            }
          } catch (error) {
            if (!disposed) {
              let messageText;
              if (error && error.name === 'AbortError') {
                messageText =
                  'Agent request timed out. Check that the local agent API is running.';
              } else if (
                error &&
                (error.name === 'AgentApiError' ||
                  error.name === 'AgentResponseError')
              ) {
                messageText = error.message;
              } else {
                messageText = `Could not contact local agent API at ${API_ENDPOINT}: ${String(error)}`;
              }
              panel.webview.postMessage({
                type: 'error',
                message: messageText,
              });
            }
          } finally {
            clearTimeout(timeout);
            isProcessing = false;
            activeController = undefined;
          }
        }
      );
      context.subscriptions.push(messageSubscription);

      panel.onDidDispose(() => {
        disposed = true;
        if (activeController) activeController.abort();
        messageSubscription.dispose();
        if (chatPanel === panel) chatPanel = undefined;
      });
    }
  );
  context.subscriptions.push(openChatPanel);

  // Sidebar question input and Ask button
  const provider = {
    resolveWebviewView(webviewView) {
      console.log('[Developer Intelligence] resolveWebviewView called');
      webviewView.webview.options = {
        enableScripts: true,
      };

      webviewView.webview.html = `
        <!DOCTYPE html>
        <html lang="en">
        <body>
          <input
            id="question"
            type="text"
            placeholder="Ask a question..."
            style="width: 100%; box-sizing: border-box;"
          />
          <br><br>
          <button id="ask" style="width: 100%;">Ask</button>

          <script>
            const vscode = acquireVsCodeApi();
            const input = document.getElementById('question');
            const button = document.getElementById('ask');

            function submitQuestion() {
              const question = input.value.trim();
              if (!question) return;

              vscode.postMessage({
                type: 'ask',
                question
              });

              input.value = '';
            }

            button.addEventListener('click', submitQuestion);

            input.addEventListener('keydown', (event) => {
              if (event.key === 'Enter') {
                submitQuestion();
              }
            });
          </script>
        </body>
        </html>
      `;

      webviewView.webview.onDidReceiveMessage(async (message) => {
        if (
          message.type !== 'ask' ||
          typeof message.question !== 'string' ||
          !message.question.trim()
        ) {
          return;
        }

        await askAgent(message.question.trim());
      });
    },
  };

  console.log('[Developer Intelligence] Registering view: developerIntelligence.askView');
  try {
    context.subscriptions.push(
      vscode.window.registerWebviewViewProvider(
        'developerIntelligence.askView',
        provider
      )
    );
    console.log('Developer Intelligence: Ask Question provider registered');
  } catch (error) {
    console.error('[Developer Intelligence] Failed to register webview view provider', error);
    throw error;
  }

  // Keep the existing Command Palette command
  const disposable = vscode.commands.registerCommand(
    'developerIntelligence.askQuestion',
    async () => {
      const question = await vscode.window.showInputBox({
        placeHolder: 'Ask a question about this repository',
      });

      if (!vscode.workspace.workspaceFolders || vscode.workspace.workspaceFolders.length === 0) {
        vscode.window.showInformationMessage(
          'No folder is open in VS Code. Open a repository folder to ask questions about its code.'
        );
      }

      if (!question || !question.trim()) {
        return;
      }

      await askAgent(question.trim());
    }
  );

  context.subscriptions.push(disposable, output);
}

function deactivate() {}

module.exports = {
  activate,
  deactivate,
};
