import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, mkdir, copyFile, readFile, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { test } from "node:test";
import { parseEnv } from "node:util";

test("configuration creates independent secrets and upgrades without rotating credentials", async () => {
  const temporaryRoot = await mkdtemp(join(tmpdir(), "forge-configure-"));
  try {
    await mkdir(join(temporaryRoot, "scripts"));
    await copyFile(
      new URL("configure.mjs", import.meta.url),
      join(temporaryRoot, "scripts/configure.mjs"),
    );
    await copyFile(
      new URL("../.env.example", import.meta.url),
      join(temporaryRoot, ".env.example"),
    );
    const run = (...args) =>
      spawnSync(process.execPath, [join(temporaryRoot, "scripts/configure.mjs"), ...args], {
        encoding: "utf8",
      });
    const envPath = join(temporaryRoot, ".env");
    assert.equal(run().status, 0);
    const original = await readFile(envPath, "utf8");
    const values = parseEnv(original);
    const secretKeys = [
      "FORGE_DATABASE_PASSWORD",
      "FORGE_MIGRATION_PASSWORD",
      "POSTGRES_PASSWORD",
      "FORGE_AUTH_SECRET",
    ];
    for (const key of secretKeys) assert.match(values[key], /^[a-f0-9]{64}$/);
    assert.equal(new Set(secretKeys.map((key) => values[key])).size, 4);
    assert.equal(run().status, 1);
    assert.equal(await readFile(envPath, "utf8"), original);

    const phaseOne =
      original
        .replace(/^FORGE_AUTH_SECRET=.*\r?\n/m, "")
        .replace(/^FORGE_PUBLIC_ORIGIN=.*\r?\n/m, "") + "CUSTOM_SETTING=keep-me\n";
    await writeFile(envPath, phaseOne);
    const result = run("--upgrade");
    assert.equal(result.status, 0);
    const updated = parseEnv(await readFile(envPath, "utf8"));
    for (const key of secretKeys.slice(0, 3)) assert.equal(updated[key], values[key]);
    assert.equal(updated.CUSTOM_SETTING, "keep-me");
    assert.equal(updated.FORGE_PUBLIC_ORIGIN, "http://localhost:3000");
    assert.match(updated.FORGE_AUTH_SECRET, /^[a-f0-9]{64}$/);
    for (const key of secretKeys) assert.ok(!result.stdout.includes(updated[key]));
    const upgraded = await readFile(envPath, "utf8");
    assert.equal(run("--upgrade").status, 0);
    assert.equal(await readFile(envPath, "utf8"), upgraded);
  } finally {
    assert.equal(dirname(resolve(temporaryRoot)), resolve(tmpdir()));
    assert.ok(basename(temporaryRoot).startsWith("forge-configure-"));
    await rm(temporaryRoot, { recursive: true, force: true });
  }
});
