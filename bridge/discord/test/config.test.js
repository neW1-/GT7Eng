import assert from "node:assert/strict";
import test from "node:test";
import { assertRuntimeConfig, parseBoolean, readConfig } from "../src/config.js";

test("readConfig applies safe defaults without credentials", () => {
  const config = readConfig({});
  assert.equal(config.python.baseUrl, "http://127.0.0.1:8001");
  assert.equal(config.audio.jobPollIntervalMs, 1000);
  assert.equal(config.audio.defaultEngineerMuted, false);
  assert.equal(config.audio.defaultMode, "quiet_driver");
  assert.equal(config.audio.autoJoinOnReady, false);
  assert.equal(config.stt.enabled, false);
  assert.equal(config.stt.sampleRate, 48000);
});

test("readConfig parses env overrides", () => {
  const config = readConfig({
    PYTHON_SERVICE_URL: "http://localhost:9000/",
    DEFAULT_ENGINEER_MUTED: "yes",
    DEFAULT_AUDIO_MODE: "wake_phrase",
    JOB_POLL_INTERVAL_MS: "250",
    AUTO_JOIN_ON_READY: "true",
    DISCORD_STT_ENABLED: "true",
    DISCORD_STT_MIN_SEGMENT_MS: "300",
    DISCORD_STT_MAX_SEGMENT_MS: "5000"
  });
  assert.equal(config.python.baseUrl, "http://localhost:9000");
  assert.equal(config.audio.defaultEngineerMuted, true);
  assert.equal(config.audio.defaultMode, "wake_phrase");
  assert.equal(config.audio.jobPollIntervalMs, 250);
  assert.equal(config.audio.autoJoinOnReady, true);
  assert.equal(config.stt.enabled, true);
  assert.equal(config.stt.minSegmentMs, 300);
  assert.equal(config.stt.maxSegmentMs, 5000);
});

test("parseBoolean rejects ambiguous values", () => {
  assert.throws(() => parseBoolean("sometimes"), /Invalid boolean/);
});

test("assertRuntimeConfig reports missing runtime-only credentials", () => {
  assert.throws(() => assertRuntimeConfig(readConfig({})), /DISCORD_TOKEN/);
});
