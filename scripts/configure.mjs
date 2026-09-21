import { randomBytes } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const root = new URL("../", import.meta.url);
let content = await readFile(new URL(".env.example", root), "utf8");
for (const name of ["FORGE_DATABASE_PASSWORD", "FORGE_MIGRATION_PASSWORD", "POSTGRES_PASSWORD"]) {
  content = content.replace(
    new RegExp(`^${name}=$`, "m"),
    `${name}=${randomBytes(32).toString("hex")}`,
  );
}
try {
  await writeFile(new URL(".env", root), content, { flag: "wx", mode: 0o600 });
  console.log(
    `Created ${fileURLToPath(new URL(".env", root))} with unique local database passwords.`,
  );
  console.log("Review ports if needed, then run: docker compose up -d --build");
} catch (error) {
  if (error.code === "EEXIST") {
    console.error(
      ".env already exists; left it unchanged. Edit it directly if configuration must change.",
    );
    process.exitCode = 1;
  } else {
    throw error;
  }
}
