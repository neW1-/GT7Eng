const LEVELS = new Map([
  ["debug", 10],
  ["info", 20],
  ["warn", 30],
  ["error", 40]
]);

export function createLogger(level = "info") {
  const threshold = LEVELS.get(level) ?? LEVELS.get("info");

  function write(method, message, meta) {
    const rank = LEVELS.get(method);
    if (rank < threshold) return;
    const suffix = meta ? ` ${JSON.stringify(meta)}` : "";
    console[method === "debug" ? "log" : method](`[discord-bridge] ${message}${suffix}`);
  }

  return {
    debug: (message, meta) => write("debug", message, meta),
    info: (message, meta) => write("info", message, meta),
    warn: (message, meta) => write("warn", message, meta),
    error: (message, meta) => write("error", message, meta)
  };
}
