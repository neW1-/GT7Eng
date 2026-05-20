import assert from "node:assert/strict";
import test from "node:test";
import { pcmToWavBuffer } from "../src/audio.js";

test("pcmToWavBuffer writes a valid wav header", () => {
  const pcm = Buffer.alloc(48000 * 2 * 2);
  const wav = pcmToWavBuffer(pcm, { sampleRate: 48000, channels: 2 });

  assert.equal(wav.subarray(0, 4).toString("ascii"), "RIFF");
  assert.equal(wav.subarray(8, 12).toString("ascii"), "WAVE");
  assert.equal(wav.subarray(36, 40).toString("ascii"), "data");
  assert.equal(wav.readUInt32LE(40), pcm.length);
});
