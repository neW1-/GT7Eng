import { ChannelType, Client, GatewayIntentBits } from "discord.js";
import {
  EndBehaviorType,
  VoiceConnectionStatus,
  entersState,
  getVoiceConnection,
  joinVoiceChannel
} from "@discordjs/voice";
import prism from "prism-media";
import {
  AudioQueue,
  createRadioCheckResource,
  createResourceFromAudioUrl,
  createResourceFromFile,
  pcmToWavBuffer
} from "./audio.js";
import { PythonServiceClient } from "./pythonClient.js";
import { BridgeState } from "./state.js";

export class DiscordVoiceBridge {
  constructor({ config, logger }) {
    this.config = config;
    this.logger = logger;
    this.client = new Client({
      intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildVoiceStates]
    });
    this.state = new BridgeState({
      mode: config.audio.defaultMode,
      engineerMuted: config.audio.defaultEngineerMuted
    });
    this.python = new PythonServiceClient(config.python);
    this.audio = new AudioQueue({ logger });
    this.jobTimer = null;
    this.receiveWatchdogTimer = null;
    this.receiveSubscriptions = new Map();
    this.intentionalDisconnect = false;
  }

  async start() {
    this.client.once("ready", () => {
      this.logger.info("Discord bridge ready", { user: this.client.user?.tag });
      this.startJobPolling();
      this.startReceiveWatchdog();
      this.audio.onPlaybackChange((isPlaying) => {
        if (isPlaying) this.stopReceiveStreams();
      });
      if (this.config.audio.autoJoinOnReady && this.config.discord.voiceChannelId) {
        this.joinChannelId(this.config.discord.voiceChannelId).catch((error) => {
          this.state.lastError = error.message;
          this.logger.error("Auto-join failed", { message: error.message });
        });
      }
    });
    this.client.on("interactionCreate", (interaction) => this.handleInteraction(interaction));
    await this.client.login(this.config.discord.token);
  }

  async stop() {
    if (this.jobTimer) clearInterval(this.jobTimer);
    if (this.receiveWatchdogTimer) clearInterval(this.receiveWatchdogTimer);
    this.disconnectVoice();
    await this.client.destroy();
  }

  startJobPolling() {
    if (this.jobTimer) clearInterval(this.jobTimer);
    this.jobTimer = setInterval(() => {
      this.pollOnce().catch((error) => {
        this.state.lastError = error.message;
        this.logger.warn("Voice job polling failed", { message: error.message });
      });
    }, this.config.audio.jobPollIntervalMs);
  }

  async pollOnce() {
    if (this.state.engineerMuted || this.state.mode === "silent") return;
    if (!this.state.voiceChannelId) return;

    const job = await this.python.nextVoiceJob();
    if (!job) return;

    try {
      const factory = await this.resourceFactoryForJob(job);
      this.audio.enqueue(factory);
      this.state.lastJobId = job.id ?? null;
      await this.python.acknowledgeJob(job.id, "played");
    } catch (error) {
      await this.python.acknowledgeJob(job.id, "failed", error.message);
      throw error;
    }
  }

  async resourceFactoryForJob(job) {
    if (job.kind === "tone") return createRadioCheckResource({ durationMs: 140 });
    if (job.audio_url) return createResourceFromAudioUrl(job.audio_url);
    if (job.audio_file) return createResourceFromFile(job.audio_file);
    if (job.text) {
      const synthesized = await this.python.synthesizeSpeech(job.text);
      if (synthesized.audio_url) return createResourceFromAudioUrl(synthesized.audio_url);
      if (synthesized.audio_file) return createResourceFromFile(synthesized.audio_file);
    }
    throw new Error("Voice job did not include playable audio or synthesizable text");
  }

  async handleInteraction(interaction) {
    if (!interaction.isChatInputCommand()) return;

    try {
      switch (interaction.commandName) {
        case "join":
          await this.handleJoin(interaction);
          break;
        case "leave":
          await this.handleLeave(interaction);
          break;
        case "status":
          await this.handleStatus(interaction);
          break;
        case "mode":
          await this.handleMode(interaction);
          break;
        case "mute_engineer":
          await this.handleMute(interaction, true);
          break;
        case "unmute_engineer":
          await this.handleMute(interaction, false);
          break;
        case "radio_check":
          await this.handleRadioCheck(interaction);
          break;
        default:
          await interaction.reply({ content: "Unknown command.", ephemeral: true });
      }
    } catch (error) {
      this.state.lastError = error.message;
      this.logger.error("Command failed", { command: interaction.commandName, message: error.message });
      const payload = { content: `Command failed: ${error.message}`, ephemeral: true };
      await this.safeInteractionResponse(interaction, payload);
    }
  }

  async handleJoin(interaction) {
    await interaction.deferReply({ ephemeral: true });
    const channel = await this.resolveVoiceChannel(interaction);
    await this.joinChannel(channel);
    await interaction.editReply(`Joined ${channel.name}.`);
  }

  async handleLeave(interaction) {
    this.disconnectVoice();
    await interaction.reply("Left voice.");
  }

  async handleStatus(interaction) {
    const snapshot = this.state.snapshot();
    let pythonHealth = "unreachable";
    try {
      const health = await this.python.health();
      pythonHealth = health.ok ? `ok (${health.status})` : `error (${health.status})`;
    } catch (error) {
      pythonHealth = `error (${error.message})`;
    }
    await interaction.reply({
      content: [
        `voice: ${snapshot.voiceChannelId ? `connected (${snapshot.voiceChannelId})` : "disconnected"}`,
        `mode: ${snapshot.mode}`,
        `engineer_muted: ${snapshot.engineerMuted}`,
        `stt_enabled: ${this.config.stt.enabled}`,
        `driver_audio_packets: ${snapshot.driverAudioPackets}`,
        `last_driver_audio_at: ${snapshot.lastDriverAudioAt ?? "none"}`,
        `python: ${pythonHealth}`,
        `last_job: ${snapshot.lastJobId ?? "none"}`,
        `last_error: ${snapshot.lastError ?? "none"}`,
        `uptime_seconds: ${snapshot.uptimeSeconds}`
      ].join("\n"),
      ephemeral: true
    });
  }

  async handleMode(interaction) {
    const mode = interaction.options.getString("mode", true);
    this.state.mode = mode;
    await this.python.setMode(mode).catch((error) => {
      this.logger.warn("Python mode update failed", { message: error.message });
    });
    await interaction.reply(`Engineer mode set to ${mode}.`);
  }

  async handleMute(interaction, muted) {
    this.state.engineerMuted = muted;
    await this.python.setEngineerMuted(muted).catch((error) => {
      this.logger.warn("Python mute update failed", { message: error.message });
    });
    await interaction.reply(muted ? "Engineer muted." : "Engineer unmuted.");
  }

  async handleRadioCheck(interaction) {
    await interaction.deferReply();
    if (!this.state.voiceChannelId) {
      const channel = await this.resolveVoiceChannel(interaction);
      await this.joinChannel(channel);
    }
    await interaction.editReply("Radio check.");
    this.audio.enqueue(createRadioCheckResource());
  }

  async safeInteractionResponse(interaction, payload) {
    try {
      if (interaction.deferred || interaction.replied) await interaction.followUp(payload);
      else await interaction.reply(payload);
    } catch (replyError) {
      this.logger.warn("Unable to send command failure response", { message: replyError.message });
    }
  }

  async resolveVoiceChannel(interaction) {
    const configuredId = this.config.discord.voiceChannelId;
    const memberChannel = interaction.member?.voice?.channel;
    const targetId = configuredId || memberChannel?.id;
    if (!targetId) {
      throw new Error("Set DISCORD_VOICE_CHANNEL_ID or join a voice channel before running /join.");
    }
    const channel = await this.client.channels.fetch(targetId);
    if (!channel || channel.type !== ChannelType.GuildVoice) {
      throw new Error(`Channel ${targetId} is not a guild voice channel.`);
    }
    return channel;
  }

  async joinChannelId(channelId) {
    const channel = await this.client.channels.fetch(channelId);
    if (!channel || channel.type !== ChannelType.GuildVoice) {
      throw new Error(`Channel ${channelId} is not a guild voice channel.`);
    }
    await this.joinChannel(channel);
    this.logger.info("Joined configured voice channel", { channelId });
  }

  async joinChannel(channel) {
    getVoiceConnection(channel.guild.id)?.destroy();
    this.stopReceiveStreams();
    this.state.voiceChannelId = null;
    const connection = joinVoiceChannel({
      channelId: channel.id,
      guildId: channel.guild.id,
      adapterCreator: channel.guild.voiceAdapterCreator,
      selfDeaf: false,
      selfMute: false,
      debug: this.config.logLevel === "debug"
    });
    connection.on("debug", (message) => {
      this.logger.debug("Voice debug", { message: redactVoiceDebug(message) });
    });
    connection.on("error", (error) => {
      this.state.lastError = error.message;
      this.logger.error("Voice connection error", { message: error.message });
    });
    connection.on("stateChange", (oldState, newState) => {
      this.logger.info("Voice connection state changed", {
        from: oldState.status,
        to: newState.status
      });
    });
    connection.on(VoiceConnectionStatus.Disconnected, () => {
      this.state.voiceChannelId = null;
      if (!this.intentionalDisconnect) {
        this.logger.warn("Voice disconnected; scheduling reconnect", { channelId: channel.id });
        setTimeout(() => {
          this.joinChannelId(channel.id).catch((error) => {
            this.state.lastError = error.message;
            this.logger.warn("Voice reconnect failed", { message: error.message });
          });
        }, 1500);
      }
    });
    await entersState(connection, VoiceConnectionStatus.Ready, 30000);
    this.logger.info("Voice connection ready", { channelId: channel.id });
    this.audio.subscribe(connection);
    this.state.voiceChannelId = channel.id;
    this.startReceiveMonitor(connection);
  }

  disconnectVoice() {
    this.intentionalDisconnect = true;
    this.audio.clear();
    this.stopReceiveStreams();
    const guilds = this.client.guilds.cache.values();
    for (const guild of guilds) {
      getVoiceConnection(guild.id)?.destroy();
    }
    this.state.voiceChannelId = null;
    setTimeout(() => {
      this.intentionalDisconnect = false;
    }, 500);
  }

  startReceiveMonitor(connection) {
    const driverUserId = this.config.discord.driverUserId;
    this.state.driverUserId = driverUserId || null;
    if (!driverUserId) {
      this.logger.warn("DISCORD_DRIVER_USER_ID is not set; inbound audio will not be monitored");
      return;
    }

    connection.receiver.speaking.on("start", (userId) => {
      if (userId !== driverUserId || this.receiveSubscriptions.has(userId) || this.audio.playing) return;
      const opusStream = connection.receiver.subscribe(userId, {
        end: {
          behavior: EndBehaviorType.AfterSilence,
          duration: 350
        }
      });
      this.receiveSubscriptions.set(userId, opusStream);
      opusStream.on("data", () => {
        this.state.driverAudioPackets += 1;
        this.state.lastDriverAudioAt = new Date().toISOString();
      });
      if (this.config.stt.enabled) {
        this.collectSpeechSegment(userId, opusStream);
      }
      opusStream.once("end", () => {
        this.receiveSubscriptions.delete(userId);
      });
      opusStream.once("error", (error) => {
        this.receiveSubscriptions.delete(userId);
        this.state.lastError = error.message;
        this.logger.warn("Driver audio receive stream failed", { message: error.message });
      });
    });
  }

  collectSpeechSegment(userId, opusStream) {
    const startedAt = new Date();
    const decoder = new prism.opus.Decoder({
      rate: this.config.stt.sampleRate,
      channels: this.config.stt.channels,
      frameSize: 960
    });
    const chunks = [];
    let pcmBytes = 0;
    const maxTimer = setTimeout(() => {
      opusStream.destroy();
    }, this.config.stt.maxSegmentMs);

    decoder.on("data", (chunk) => {
      if (this.audio.playing) return;
      chunks.push(chunk);
      pcmBytes += chunk.length;
    });
    decoder.once("error", (error) => {
      this.state.lastError = error.message;
      this.logger.warn("Driver audio decode failed", { message: error.message });
    });
    opusStream.once("end", () => {
      clearTimeout(maxTimer);
      decoder.destroy();
      const endedAt = new Date();
      this.submitSpeechSegment({ userId, startedAt, endedAt, chunks, pcmBytes }).catch((error) => {
        this.state.lastError = error.message;
        this.logger.warn("Speech segment submit failed", { message: error.message });
      });
    });
    opusStream.pipe(decoder);
  }

  async submitSpeechSegment({ userId, startedAt, endedAt, chunks, pcmBytes }) {
    const bytesPerSecond = this.config.stt.sampleRate * this.config.stt.channels * 2;
    const durationMs = (pcmBytes / bytesPerSecond) * 1000;
    if (durationMs < this.config.stt.minSegmentMs) return;
    const wav = pcmToWavBuffer(Buffer.concat(chunks), {
      sampleRate: this.config.stt.sampleRate,
      channels: this.config.stt.channels
    });
    const result = await this.python.postAudioSegment({
      userId,
      startedAt: startedAt.toISOString(),
      endedAt: endedAt.toISOString(),
      sampleRate: this.config.stt.sampleRate,
      channels: this.config.stt.channels,
      audio: wav
    });
    this.logger.info("Speech segment handled", {
      transcript: result.transcript || "",
      intent: result.command?.intent || "none",
      confidence: result.command?.confidence ?? result.confidence ?? 0
    });
  }

  stopReceiveStreams() {
    for (const stream of this.receiveSubscriptions.values()) {
      stream.destroy();
    }
    this.receiveSubscriptions.clear();
  }

  startReceiveWatchdog() {
    if (this.receiveWatchdogTimer) clearInterval(this.receiveWatchdogTimer);
    this.receiveWatchdogTimer = setInterval(() => {
      if (!this.state.voiceChannelId || !this.config.discord.driverUserId || this.audio.playing) return;
      if (!this.state.lastDriverAudioAt) return;
      const age = Date.now() - Date.parse(this.state.lastDriverAudioAt);
      if (age > this.config.audio.receiveWatchdogMs) {
        this.logger.warn("No driver audio received recently", { ageMs: age });
      }
    }, Math.min(this.config.audio.receiveWatchdogMs, 30000));
  }
}

function redactVoiceDebug(message) {
  return String(message)
    .replace(/"token":"[^"]+"/g, '"token":"<redacted>"')
    .replace(/"secret_key":\[[^\]]+\]/g, '"secret_key":"<redacted>"')
    .replace(/"secretKey":\{[^}]+\}/g, '"secretKey":"<redacted>"')
    .replace(/"media_session_id":"[^"]+"/g, '"media_session_id":"<redacted>"');
}
