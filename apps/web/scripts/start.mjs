import { cpSync, existsSync } from "node:fs";
import { spawn } from "node:child_process";
import path from "node:path";
const root = process.cwd();
const standalone = path.join(root, ".next/standalone");
if (!existsSync(path.join(standalone, "server.js"))) {
  throw new Error("Run npm run build before npm run start");
}
cpSync(path.join(root, ".next/static"), path.join(standalone, ".next/static"), {
  recursive: true,
});
const child = spawn(process.execPath, [path.join(standalone, "server.js")], {
  stdio: "inherit",
  env: {
    ...process.env,
    PORT: process.env.PORT || "3100",
    HOSTNAME: process.env.LANGAI_WEB_HOST || "127.0.0.1",
  },
});
for (const signal of ["SIGTERM", "SIGINT"])
  process.on(signal, () => child.kill(signal));
child.on("exit", (code) => process.exit(code || 0));
