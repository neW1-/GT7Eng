import { DiscordVoiceBridge } from "./bot.js";
import { assertRuntimeConfig, readConfig } from "./config.js";
import { createLogger } from "./logger.js";

const config = readConfig();
assertRuntimeConfig(config);

const logger = createLogger(config.logLevel);
const bridge = new DiscordVoiceBridge({ config, logger });

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);

await bridge.start();

async function shutdown() {
  logger.info("Shutting down Discord bridge");
  await bridge.stop();
  process.exit(0);
}
