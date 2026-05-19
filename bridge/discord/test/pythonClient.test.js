import assert from "node:assert/strict";
import test from "node:test";
import { PythonServiceClient } from "../src/pythonClient.js";

test("PythonServiceClient sends bearer token and JSON body", async () => {
  let captured;
  const client = new PythonServiceClient({
    baseUrl: "http://python.local",
    token: "secret",
    fetchImpl: async (url, init) => {
      captured = { url, init };
      return new Response("{}", { status: 200 });
    }
  });

  await client.setMode("wake_phrase");

  assert.equal(captured.url, "http://python.local/discord/mode");
  assert.equal(captured.init.method, "POST");
  assert.equal(captured.init.headers.authorization, "Bearer secret");
  assert.equal(captured.init.headers["content-type"], "application/json");
  assert.equal(captured.init.body, JSON.stringify({ mode: "wake_phrase" }));
});

test("nextVoiceJob returns first job", async () => {
  const client = new PythonServiceClient({
    baseUrl: "http://python.local",
    fetchImpl: async () =>
      new Response(JSON.stringify({ jobs: [{ id: "1" }, { id: "2" }] }), { status: 200 })
  });

  assert.deepEqual(await client.nextVoiceJob(), { id: "1" });
});
