import { expect, test } from "./offline-fixture";
import { createHash } from "node:crypto";

const entry = (
  id: string,
  headword: string,
  definitions: string[],
  alternate_spellings: string[] = [],
) => ({
  id,
  source_id: "source-1",
  headword,
  definitions,
  alternate_spellings,
  part_of_speech: "",
  dialect: "",
});
const payload = JSON.stringify({
  engine: "langai-lexical-v1",
  language: { id: "synthetic", name: "Synthetic phrase dictionary" },
  sources: [
    {
      id: "source-1",
      filename: "synthetic.csv",
      sha256: "a".repeat(64),
      governance: {
        owner: "Fixture author",
        custodian: "",
        source: "Synthetic test data",
        licence: "CC0",
        attribution: "Fixture attribution",
        training_allowed: true,
        commercial_use_allowed: false,
        redistribution_allowed: false,
      },
    },
  ],
  entries: [
    entry("1", "synthetic greeting", ["hello there"], ["synthetic hello"]),
    entry("2", "synthetic farewell", ["goodbye now"]),
    entry("3", "synthetic bank", ["river edge"]),
    entry("4", "synthetic bank", ["financial institution"]),
    entry("5", "synthetic café", ["a café"]),
    entry("6", "synthetic cafe", ["a different entry"]),
    entry("7", "synthetic <script>alert(1)</script>", ["literal markup"]),
  ],
});
const pack = JSON.stringify({
  format: "langai-offline-v1",
  payload,
  sha256: createHash("sha256").update(payload).digest("hex"),
});
const file = (text = pack) => ({
  name: "synthetic.langai.json",
  mimeType: "application/json",
  buffer: Buffer.from(text),
});

test("phone dictionary persists across offline restart, keeps ambiguity and deletes locally", async ({
  page,
  context,
  offlineApp,
  browserName,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(offlineApp.url);
  await expect(page.locator("#availability")).toContainText(
    "Offline app ready",
  );
  await page.locator("#pack").setInputFiles(file());
  await expect(page.locator("#availability")).toContainText(
    "Ready for offline use",
  );
  await page.evaluate(async () => {
    if (!navigator.serviceWorker.controller)
      await new Promise<void>((resolve) =>
        navigator.serviceWorker.addEventListener(
          "controllerchange",
          () => resolve(),
          { once: true },
        ),
      );
  });
  await offlineApp.stop();
  if (browserName !== "webkit") await context.setOffline(true);
  // A new document must reload its scripts, worker and saved data without the server.
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Synthetic phrase dictionary" }),
  ).toBeVisible();
  await expect(page.locator("#availability")).toContainText(
    "Ready for offline use",
  );
  const query = async (text: string) => {
    await page.getByLabel("Word, phrase or meaning").fill(text);
    await page.getByRole("button", { name: "Find matches" }).click();
    await expect(page.locator("#result-status")).not.toContainText("Searching");
  };
  await query("  SYNTHETIC   HELLO  ");
  await expect(page.locator("#result-status")).toHaveText(
    "Exact dictionary match",
  );
  await expect(page.locator("#results")).toContainText("hello there");
  await query("synthetic bank");
  await expect(page.locator("#result-status")).toContainText(
    "Multiple exact matches",
  );
  await expect(page.locator(".match")).toHaveCount(2);
  await page.getByLabel("Search direction").selectOption("meaning-to-word");
  await query("goodbye now");
  await expect(page.locator("#results")).toContainText("synthetic farewell");
  await query("hello there friend");
  await expect(page.locator("#result-status")).toContainText(
    "Possible matches",
  );
  await query("unrelated quasar");
  await expect(page.locator("#result-status")).toContainText(
    "No dictionary match",
  );
  await page.getByLabel("Search direction").selectOption("word-to-meaning");
  await query("synthetic cafe\u0301");
  await expect(page.locator(".match")).toHaveCount(1);
  await expect(page.locator("#results")).toContainText("synthetic café");
  await query("synthetic <script>alert(1)</script>");
  await expect(page.locator("#results script")).toHaveCount(0);
  await expect(page.locator("#results")).toContainText("literal markup");
  await page
    .locator("#pack")
    .setInputFiles(file(pack.replace("hello there", "tampered")));
  await expect(page.getByRole("alert")).toContainText("integrity check failed");
  await query("synthetic greeting");
  await expect(page.locator("#results")).toContainText("hello there");
  await page.getByRole("button", { name: "Remove from phone" }).click();
  await expect(page.locator("#dictionary")).toBeHidden();
  await page.reload();
  await expect(page.locator("#availability")).toContainText(
    "Import a dictionary",
  );
  await expect(page.locator("#dictionary")).toBeHidden();
  expect(errors).toEqual([]);
  const cached = await page.evaluate(async () =>
    (
      await Promise.all(
        (await caches.keys()).map(async (key) =>
          (await (await caches.open(key)).keys()).map(
            (r) => new URL(r.url).pathname,
          ),
        ),
      )
    ).flat(),
  );
  expect(cached.every((path) => path.startsWith("/offline/"))).toBe(true);
});

test("rejects unsupported or malformed packs without claiming offline dictionary readiness", async ({
  page,
  offlineApp,
}) => {
  await page.goto(offlineApp.url);
  await expect(page.locator("#availability")).toContainText(
    "Offline app ready",
  );
  await page.locator("#pack").setInputFiles(file('{"format":"unknown"}'));
  await expect(page.getByRole("alert")).toContainText(
    "unsupported dictionary pack",
  );
  await expect(page.locator("#dictionary")).toBeHidden();
  await expect(page.locator("#availability")).not.toContainText(
    "Ready for offline use",
  );
});
