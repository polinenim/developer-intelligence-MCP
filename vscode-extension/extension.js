const vscode = require('vscode');

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
  const disposable = vscode.commands.registerCommand('developerIntelligence.askQuestion', () => {
    vscode.window.showInformationMessage('Developer Intelligence: Ask Question command executed.');
  });

  context.subscriptions.push(disposable);
}

function deactivate() {}

module.exports = {
  activate,
  deactivate
};
