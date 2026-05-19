import { REST, Routes } from "discord.js";
import { buildSlashCommands } from "./commands.js";
import { assertRuntimeConfig, readConfig } from "./config.js";

const config = readConfig();
assertRuntimeConfig(config);

const rest = new REST({ version: "10" }).setToken(config.discord.token);
const commands = buildSlashCommands();

if (config.commands.registerScope === "global") {
  await rest.put(Routes.applicationCommands(config.discord.clientId), { body: commands });
  console.log(`Registered ${commands.length} global Discord commands.`);
} else {
  await rest.put(Routes.applicationGuildCommands(config.discord.clientId, config.discord.guildId), {
    body: commands
  });
  console.log(`Registered ${commands.length} guild Discord commands for ${config.discord.guildId}.`);
}
