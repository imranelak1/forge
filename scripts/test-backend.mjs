import { randomBytes } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { parseEnv } from "node:util";

const root = fileURLToPath(new URL("../", import.meta.url));
const config = parseEnv(readFileSync(new URL("../.env", import.meta.url), "utf8"));
const project = config.COMPOSE_PROJECT_NAME || "forge";
const database = `forge_${randomBytes(6).toString("hex")}_test`;

function run(args, { allowFailure = false } = {}) {
  const result = spawnSync("docker", args, { cwd: root, stdio: "inherit", shell: false });
  if (result.error) throw result.error;
  if (result.status !== 0 && !allowFailure)
    throw new Error(`Docker command failed (exit ${result.status})`);
  return result.status;
}

let created = false;
try {
  run(["compose", "up", "-d", "--wait", "postgres"]);
  run([
    "build",
    "--target",
    "test",
    "-t",
    `${project}-api-test`,
    "-f",
    "infrastructure/docker/api.Dockerfile",
    "apps/api",
  ]);
  run(["compose", "exec", "-T", "postgres", "createdb", "-U", "forge_bootstrap", database]);
  created = true;
  run([
    "compose",
    "exec",
    "-T",
    "-e",
    `POSTGRES_DB=${database}`,
    "postgres",
    "bash",
    "/docker-entrypoint-initdb.d/10-roles.sh",
  ]);
  run([
    "run",
    "--rm",
    "--network",
    `${project}_default`,
    "--env-file",
    ".env",
    // Test fixtures own provider credentials; never inherit live OAuth clients.
    "-e",
    "FORGE_GITHUB_CLIENT_ID=",
    "-e",
    "FORGE_GITHUB_CLIENT_SECRET=",
    "-e",
    "FORGE_GOOGLE_CLIENT_ID=",
    "-e",
    "FORGE_GOOGLE_CLIENT_SECRET=",
    "-e",
    "FORGE_ENVIRONMENT=test",
    "-e",
    "FORGE_DATABASE_HOST=postgres",
    "-e",
    "FORGE_DATABASE_PORT=5432",
    "-e",
    `FORGE_DATABASE_NAME=${database}`,
    "-e",
    "FORGE_RUN_DB_TESTS=1",
    `${project}-api-test`,
  ]);
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
} finally {
  // Only the fresh, generated test database is eligible for removal.
  if (created && /^forge_[a-f0-9]{12}_test$/.test(database)) {
    const result = run(
      ["compose", "exec", "-T", "postgres", "dropdb", "-U", "forge_bootstrap", "--force", database],
      { allowFailure: true },
    );
    if (result !== 0) process.exitCode = 1;
  }
}
