import { Readable } from "node:stream";
import ffmpegPath from "ffmpeg-static";
import prism from "prism-media";
import {
  AudioPlayerStatus,
  StreamType,
  createAudioPlayer,
  createAudioResource,
  entersState
} from "@discordjs/voice";

if (ffmpegPath) {
  process.env.FFMPEG_PATH = ffmpegPath;
}

export class AudioQueue {
  constructor({ logger }) {
    this.logger = logger;
    this.player = createAudioPlayer();
    this.queue = [];
    this.playing = false;
    this.playbackListeners = [];

    this.player.on("error", (error) => {
      this.logger.error("Audio player error", { message: error.message });
      this.playing = false;
      this.emitPlayback(false);
      this.playNext();
    });

    this.player.on(AudioPlayerStatus.Idle, () => {
      if (this.playing) this.logger.info("Audio playback finished");
      this.playing = false;
      this.emitPlayback(false);
      this.playNext();
    });
  }

  subscribe(connection) {
    const subscription = connection.subscribe(this.player);
    this.logger.info("Audio player subscribed to voice connection", {
      subscribed: Boolean(subscription)
    });
  }

  enqueue(resourceFactory) {
    this.queue.push(resourceFactory);
    this.logger.info("Queued audio resource", { queueLength: this.queue.length });
    this.playNext();
  }

  clear() {
    this.queue = [];
    this.player.stop(true);
  }

  onPlaybackChange(listener) {
    this.playbackListeners.push(listener);
  }

  emitPlayback(isPlaying) {
    for (const listener of this.playbackListeners) {
      listener(isPlaying);
    }
  }

  async playNext() {
    if (this.playing || this.queue.length === 0) return;
    const factory = this.queue.shift();
    try {
      const resource = await factory();
      this.playing = true;
      this.emitPlayback(true);
      this.logger.info("Starting audio playback");
      this.player.play(resource);
    } catch (error) {
      this.logger.error("Unable to create audio resource", { message: error.message });
      this.playing = false;
      this.playNext();
    }
  }
}

export function createResourceFromAudioUrl(url) {
  return async () => {
    const response = await fetch(url);
    if (!response.ok || !response.body) {
      throw new Error(`Audio fetch failed with HTTP ${response.status}`);
    }
    return createTranscodedResource(Readable.fromWeb(response.body));
  };
}

export function createResourceFromFile(path) {
  return () => createTranscodedResource(path);
}

export function createRadioCheckResource({ frequency = 880, durationMs = 550 } = {}) {
  return () =>
    createAudioResource(Readable.from([generateTonePcm({ frequency, durationMs })]), {
      inputType: StreamType.Raw
    });
}

export async function waitForPlayerIdle(player, timeoutMs = 30000) {
  await entersState(player, AudioPlayerStatus.Idle, timeoutMs);
}

function generateTonePcm({ frequency = 880, durationMs = 550, sampleRate = 48000 } = {}) {
  const samples = Math.floor((sampleRate * durationMs) / 1000);
  const buffer = Buffer.alloc(samples * 2 * 2);
  for (let i = 0; i < samples; i += 1) {
    const amplitude = Math.sin((2 * Math.PI * frequency * i) / sampleRate) * 0.25;
    const sample = Math.max(-1, Math.min(1, amplitude)) * 32767;
    buffer.writeInt16LE(sample, i * 4);
    buffer.writeInt16LE(sample, i * 4 + 2);
  }
  return buffer;
}

export function pcmToWavBuffer(pcm, { sampleRate = 48000, channels = 2, bitDepth = 16 } = {}) {
  const blockAlign = (channels * bitDepth) / 8;
  const byteRate = sampleRate * blockAlign;
  const header = Buffer.alloc(44);
  header.write("RIFF", 0);
  header.writeUInt32LE(36 + pcm.length, 4);
  header.write("WAVE", 8);
  header.write("fmt ", 12);
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20);
  header.writeUInt16LE(channels, 22);
  header.writeUInt32LE(sampleRate, 24);
  header.writeUInt32LE(byteRate, 28);
  header.writeUInt16LE(blockAlign, 32);
  header.writeUInt16LE(bitDepth, 34);
  header.write("data", 36);
  header.writeUInt32LE(pcm.length, 40);
  return Buffer.concat([header, pcm]);
}

function createTranscodedResource(input) {
  const ffmpeg = new prism.FFmpeg({
    args: [
      "-analyzeduration",
      "0",
      "-loglevel",
      "0",
      "-i",
      input instanceof Readable ? "pipe:0" : input,
      "-f",
      "s16le",
      "-ar",
      "48000",
      "-ac",
      "2"
    ]
  });

  if (input instanceof Readable) {
    input.pipe(ffmpeg);
  }

  return createAudioResource(ffmpeg, { inputType: StreamType.Raw });
}
