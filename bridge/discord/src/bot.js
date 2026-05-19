import { ChannelType, Client, GatewayIntentBits } from "discord.js";
import { EndBehaviorType, VoiceConnectionStatus, getVoiceConnection, joinVoiceChannel } from "@discordjs/voice";
import {
  AudioQueue,
  createRadioCheckResource,
  createResourceFromAudioUrl,
  createResourceFromFile
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
    this.receiveSubscriptions = new Map();
  }

  async start() {
    this.client.once("ready", () => {
      this.logger.info("Discord bridge ready", { user: this.client.user?.tag });
      this.startJobPolling();
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
      if (interaction.deferred || interaction.replied) await interaction.followUp(payload);
      else await interaction.reply(payload);
    }
  }

  async handleJoin(interaction) {
    const channel = await this.resolveVoiceChannel(interaction);
    await this.joinChannel(channel);
    await interaction.reply(`Joined ${channel.name}.`);
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
    if (!this.state.voiceChannelId) {
      await this.handleJoin(interaction);
    } else {
      await interaction.reply("Radio check.");
    }
    this.audio.enqueue(createRadioCheckResource());
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
    const connection = joinVoiceChannel({
      channelId: channel.id,
      guildId: channel.guild.id,
      adapterCreator: channel.guild.voiceAdapterCreator,
      selfDeaf: false
    });
    connection.on(VoiceConnectionStatus.Disconnected, () => {
      this.state.voiceChannelId = null;
    });
    this.audio.subscribe(connection);
    this.state.voiceChannelId = channel.id;
    this.startReceiveMonitor(connection);
  }

  disconnectVoice() {
    this.audio.clear();
    for (const stream of this.receiveSubscriptions.values()) {
      stream.destroy();
    }
    this.receiveSubscriptions.clear();
    const guilds = this.client.guilds.cache.values();
    for (const guild of guilds) {
      getVoiceConnection(guild.id)?.destroy();
    }
    this.state.voiceChannelId = null;
  }

  startReceiveMonitor(connection) {
    const driverUserId = this.config.discord.driverUserId;
    this.state.driverUserId = driverUserId || null;
    if (!driverUserId) {
      this.logger.warn("DISCORD_DRIVER_USER_ID is not set; inbound audio will not be monitored");
      return;
    }

    connection.receiver.speaking.on("start", (userId) => {
      if (userId !== driverUserId || this.receiveSubscriptions.has(userId)) return;
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
}
