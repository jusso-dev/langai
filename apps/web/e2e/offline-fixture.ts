import { test as base, expect } from "@playwright/test";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";
import type { AddressInfo } from "node:net";

// Each test owns an origin it can actually stop. WebKit's offline emulation
// incorrectly blocks even service-worker responses (Playwright issue #42775).
export const test = base.extend<{
  offlineApp: { url: string; stop: () => Promise<void> };
}>({
  offlineApp: async ({}, use) => {
    const types: Record<string, string> = {
      ".html": "text/html",
      ".css": "text/css",
      ".js": "text/javascript",
      ".mjs": "text/javascript",
      ".webmanifest": "application/manifest+json",
      ".png": "image/png",
      ".svg": "image/svg+xml",
    };
    const server = createServer(async (request, response) => {
      const name = new URL(request.url || "/", "http://localhost").pathname;
      if (!/^\/offline\/[a-z0-9.-]+$/.test(name)) {
        response.writeHead(404).end();
        return;
      }
      try {
        const data = await readFile(path.join(process.cwd(), "public", name));
        response.writeHead(200, {
          "Content-Type":
            types[path.extname(name)] || "application/octet-stream",
        });
        response.end(data);
      } catch {
        response.writeHead(404).end();
      }
    });
    await new Promise<void>((resolve) =>
      server.listen(0, "127.0.0.1", resolve),
    );
    const stop = async () => {
      if (!server.listening) return;
      server.closeAllConnections();
      await new Promise<void>((resolve, reject) =>
        server.close((error) => (error ? reject(error) : resolve())),
      );
    };
    try {
      await use({
        url: `http://127.0.0.1:${(server.address() as AddressInfo).port}/offline/index.html`,
        stop,
      });
    } finally {
      await stop();
    }
  },
});
export { expect };
