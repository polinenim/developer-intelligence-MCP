const API_ENDPOINT = 'http://127.0.0.1:8765/ask';
const REQUEST_TIMEOUT_MS = 180_000;

function createAgentError(name, message) {
  const error = new Error(message);
  error.name = name;
  return error;
}

async function requestAgentAnswer(
  body,
  { fetchImpl = fetch, timeoutMs = REQUEST_TIMEOUT_MS, signal } = {}
) {
  const controller = new AbortController();
  const abortRequest = () => controller.abort();
  if (signal) {
    if (signal.aborted) {
      controller.abort();
    } else {
      signal.addEventListener('abort', abortRequest, { once: true });
    }
  }
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetchImpl(API_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    const responseText = (await response.text()).trim();
    let result;

    if (responseText) {
      try {
        result = JSON.parse(responseText);
      } catch {
        result = null;
      }
    }

    if (!response.ok) {
      const errorMessage =
        result && typeof result.error === 'string'
          ? result.error
          : responseText || `Request failed (${response.status})`;
      throw createAgentError('AgentApiError', `Agent API error: ${errorMessage}`);
    }
    if (
      !responseText ||
      !result ||
      typeof result.answer !== 'string'
    ) {
      throw createAgentError(
        'AgentResponseError',
        'Agent API returned an invalid response.'
      );
    }

    return result.answer;
  } finally {
    clearTimeout(timeout);
    if (signal) signal.removeEventListener('abort', abortRequest);
  }
}

function sendAnswerToWebview(webview, answer) {
  return webview.postMessage({ type: 'answer', answer });
}

module.exports = {
  API_ENDPOINT,
  REQUEST_TIMEOUT_MS,
  requestAgentAnswer,
  sendAnswerToWebview,
};
