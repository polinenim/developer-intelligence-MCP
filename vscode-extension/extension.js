const vscode = require('vscode');

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
  const disposable = vscode.commands.registerCommand('developerIntelligence.askQuestion', async () => {
    const question = await vscode.window.showInputBox({
      placeHolder: 'Ask a question about this repository',
    });
    if (!question) {
      return;
    }

    const endpoint = 'http://127.0.0.1:8765/ask';
    try {
      const resp = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      });
      if (!resp.ok) {
        const text = await resp.text();
        vscode.window.showErrorMessage('Agent error: ' + text);
        return;
      }
      const json = await resp.json();
      const answer = json.answer || JSON.stringify(json);
      vscode.window.showInformationMessage('Agent: ' + answer);
    } catch (err) {
      vscode.window.showErrorMessage('Could not contact local agent API: ' + String(err));
    }
  });

  context.subscriptions.push(disposable);
}

function deactivate() {}

module.exports = {
  activate,
  deactivate,
};
