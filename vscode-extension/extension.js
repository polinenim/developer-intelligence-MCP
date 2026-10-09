
const vscode = require('vscode');

const API_ENDPOINT = 'http://127.0.0.1:8765/ask';

function formatAnswer(answer) {
  if (!answer) {
    return 'No answer returned.';
  }

  return answer
    .trim()
    .replace(/^Based on the repository.*?:\s*/i, '')
    .replace(/\n{3,}/g, '\n\n');
}

function activate(context) {
  console.log('[Developer Intelligence] Extension activated');

  const output = vscode.window.createOutputChannel(
    'Developer Intelligence'
  );

  async function askAgent(question) {
    try {
      const resp = await fetch(API_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      });

      if (!resp.ok) {
        const errorText = await resp.text();
        vscode.window.showErrorMessage('Agent error: ' + errorText);
        return;
      }

      const json = await resp.json();
      const answer = formatAnswer(
        json.answer || 'No answer returned.'
      );

      output.appendLine(`You: ${question}`);
      output.appendLine(`Agent: ${answer}`);
      output.appendLine('');

      output.show(true);
    } catch (err) {
      vscode.window.showErrorMessage(
        'Could not contact local agent API: ' + String(err)
      );
    }
  }

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
