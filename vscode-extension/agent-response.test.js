const assert = require('node:assert/strict');
const test = require('node:test');

const {
  REQUEST_TIMEOUT_MS,
  requestAgentAnswer,
  sendAnswerToWebview,
} = require('./agent-response');

test('accepts and returns a delayed HTTP 200 answer for the chat panel', async () => {
  assert.ok(REQUEST_TIMEOUT_MS > 127_000);
  let requestOptions;
  const webviewMessages = [];

  const answer = await requestAgentAnswer(
    { question: 'test question' },
    {
      timeoutMs: 100,
      fetchImpl: async (url, options) => {
        requestOptions = { url, ...options };
        await new Promise((resolve) => setTimeout(resolve, 25));
        return {
          ok: true,
          status: 200,
          text: async () => JSON.stringify({ answer: 'result.answer text' }),
        };
      },
    }
  );

  assert.equal(answer, 'result.answer text');
  assert.equal(requestOptions.method, 'POST');
  assert.deepEqual(JSON.parse(requestOptions.body), {
    question: 'test question',
  });
  assert.equal(requestOptions.signal.aborted, false);
  const delivered = await sendAnswerToWebview(
    {
      postMessage: async (message) => {
        webviewMessages.push(message);
        return true;
      },
    },
    answer
  );
  assert.equal(delivered, true);
  assert.deepEqual(webviewMessages, [
    { type: 'answer', answer: 'result.answer text' },
  ]);
});

test('reports malformed successful responses rather than ignoring them', async () => {
  await assert.rejects(
    requestAgentAnswer(
      { question: 'test question' },
      {
        fetchImpl: async () => ({
          ok: true,
          status: 200,
          text: async () => JSON.stringify({ result: 'answer' }),
        }),
      }
    ),
    { name: 'AgentResponseError' }
  );
});

test('preserves useful plain-text errors from unsuccessful API responses', async () => {
  await assert.rejects(
    requestAgentAnswer(
      { question: 'test question' },
      {
        fetchImpl: async () => ({
          ok: false,
          status: 502,
          text: async () => 'Agent backend unavailable',
        }),
      }
    ),
    {
      name: 'AgentApiError',
      message: 'Agent API error: Agent backend unavailable',
    }
  );
});
