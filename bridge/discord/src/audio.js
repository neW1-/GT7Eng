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

    this.player.on("error", (error) => {
      this.logger.error("Audio player error", { message: error.message });
      this.playing = false;
      this.playNext();
    });

    this.player.on(AudioPlayerStatus.Idle, () => {
      this.playing = false;
      this.playNext();
    });
  }

  subscribe(connection) {
    connection.subscribe(this.player);
  }

  enqueue(resourceFactory) {
    this.queue.push(resourceFactory);
    this.playNext();
  }

  clear() {
    this.queue = [];
    this.player.stop(true);
  }

  async playNext() {
    if (this.playing || this.queue.length === 0) return;
    const factory = this.queue.shift();
    try {
      const resource = await factory();
      this.playing = true;
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

export function createRadioCheckResource() {
  return () =>
    createAudioResource(Readable.from(generateTonePcm()), {
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
