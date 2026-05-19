import { SlashCommandBuilder } from "discord.js";

export const MODES = ["wake_phrase", "quiet_driver", "silent"];

export function buildSlashCommands() {
  return [
    new SlashCommandBuilder().setName("join").setDescription("Join the configured or current voice channel."),
    new SlashCommandBuilder().setName("leave").setDescription("Leave the active voice channel."),
    new SlashCommandBuilder().setName("status").setDescription("Show Discord bridge and Python service status."),
    new SlashCommandBuilder()
      .setName("mode")
      .setDescription("Set race engineer audio mode.")
      .addStringOption((option) =>
        option
          .setName("mode")
          .setDescription("Playback mode")
          .setRequired(true)
          .addChoices(...MODES.map((mode) => ({ name: mode, value: mode })))
      ),
    new SlashCommandBuilder().setName("mute_engineer").setDescription("Mute engineer TTS playback."),
    new SlashCommandBuilder().setName("unmute_engineer").setDescription("Unmute engineer TTS playback."),
    new SlashCommandBuilder().setName("radio_check").setDescription("Play a short test tone in voice.")
  ].map((command) => command.toJSON());
}

export function commandNames() {
  return buildSlashCommands().map((command) => command.name);
}
