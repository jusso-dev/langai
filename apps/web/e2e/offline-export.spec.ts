import { expect, test } from "./offline-fixture";

test("workspace exports a one-entry pack that the offline app can use", async ({
  page,
  context,
  offlineApp,
  browserName,
}) => {
  const token = process.env.LANGAI_E2E_TOKEN;
  test.skip(
    !token,
    "Requires a disposable API deployment and LANGAI_E2E_TOKEN",
  );
  const post = (
    url: string,
    options: Parameters<typeof page.request.post>[1] = {},
  ) =>
    page.request.post(url, {
      ...options,
      headers: {
        Origin: new URL(process.env.LANGAI_E2E_URL || "http://127.0.0.1:3100")
          .origin,
      },
    });
  const session = await post("/api/session", { data: { token } });
  expect(session.ok()).toBe(true);
  const languageResponse = await post("/api/proxy/languages", {
    data: { name: `Synthetic offline export ${Date.now()}` },
  });
  expect(languageResponse.ok()).toBe(true);
  const language = await languageResponse.json();
  const sourceResponse = await post(
    `/api/proxy/languages/${language.id}/dictionaries`,
    {
      multipart: {
        file: {
          name: "synthetic-offline.csv",
          mimeType: "text/csv",
          buffer: Buffer.from(
            "word,definition\nsynthetic phrase,a portable meaning\n",
          ),
        },
        governance: JSON.stringify({
          owner: "Fixture owner",
          source: "Synthetic engineering data",
          licence: "CC0",
          training_allowed: true,
        }),
      },
    },
  );
  expect(sourceResponse.ok()).toBe(true);
  const source = await sourceResponse.json();
  expect(
    (
      await post(`/api/proxy/dictionaries/${source.id}/import`, {
        data: { mapping: source.suggested_mapping },
      })
    ).ok(),
  ).toBe(true);
  expect(
    (await post(`/api/proxy/dictionaries/${source.id}/approve`)).ok(),
  ).toBe(true);
  await page.goto(`/languages/${language.id}/offline`);
  await page.getByRole("checkbox", { name: "synthetic-offline.csv" }).check();
  const downloadEvent = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export phone dictionary" }).click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toBe(
    `dictionary-${language.id}.langai.json`,
  );
  await page.goto(offlineApp.url);
  await expect(page.locator("#availability")).toContainText(
    "Offline app ready",
  );
  await page.locator("#pack").setInputFiles((await download.path())!);
  await expect(page.locator("#availability")).toContainText(
    "Ready for offline use",
  );
  await expect(page.locator("#details")).toContainText("1 entries");
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
  await page.reload();
  await page.getByLabel("Word, phrase or meaning").fill("synthetic phrase");
  await page.getByRole("button", { name: "Find matches" }).click();
  await expect(page.locator("#result-status")).toHaveText(
    "Exact dictionary match",
  );
  await expect(page.locator("#results")).toContainText("a portable meaning");
});
