import { randomBytes } from "node:crypto";
import { chown, mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { parseEnv } from "node:util";

const args = process.argv.slice(2);
if (args.some((arg) => arg !== "--upgrade")) {
  console.error("Usage: node scripts/configure.mjs [--upgrade]");
  process.exit(1);
}
const upgrade = args.includes("--upgrade");
const root = new URL("../", import.meta.url);
const target = new URL(".env", root);
const template = await readFile(new URL(".env.example", root), "utf8");
const defaults = parseEnv(template);
const secretNames = [
  "FORGE_DATABASE_PASSWORD",
  "FORGE_MIGRATION_PASSWORD",
  "POSTGRES_PASSWORD",
  "FORGE_AUTH_SECRET",
];
const uid = process.getuid?.() || 10001;
const gid = process.getgid?.() || 10001;
defaults.FORGE_RUNTIME_UID = String(uid);
defaults.FORGE_RUNTIME_GID = String(gid);

let existing;
try {
  existing = await readFile(target, "utf8");
} catch (error) {
  if (error.code !== "ENOENT") throw error;
}
if (existing !== undefined && !upgrade) {
  console.error(".env already exists; left it unchanged. Use --upgrade to add missing settings.");
  process.exit(1);
}

let content = existing ?? template;
const configured = parseEnv(content);
const added = [];
for (const [name, defaultValue] of Object.entries(defaults)) {
  const present = Object.hasOwn(configured, name);
  if (present && (configured[name] || !secretNames.includes(name))) continue;
  const value = secretNames.includes(name) ? randomBytes(32).toString("hex") : defaultValue;
  if (present) {
    content = content.replace(
      new RegExp(`^(?:export\\s+)?${name}\\s*=.*$`, "m"),
      `${name}=${value}`,
    );
  } else {
    content = `${content.trimEnd()}\n${name}=${value}\n`;
  }
  added.push(name);
}
if (existing === undefined) {
  content = content
    .replace(/^FORGE_RUNTIME_UID=.*$/m, `FORGE_RUNTIME_UID=${uid}`)
    .replace(/^FORGE_RUNTIME_GID=.*$/m, `FORGE_RUNTIME_GID=${gid}`);
}
await writeFile(target, content, { flag: existing === undefined ? "wx" : "w", mode: 0o600 });
const outbox = new URL(".local/mail/", root);
await mkdir(outbox, { recursive: true, mode: 0o700 });
if (process.getuid?.() === 0) await chown(outbox, uid, gid);
console.log(`${existing === undefined ? "Created" : "Updated"} ${fileURLToPath(target)}.`);
console.log(`Configured ${added.length} missing settings; existing credentials were preserved.`);
console.log("Local emails: .local/mail/*.eml. Start Forge: docker compose up -d --build");
