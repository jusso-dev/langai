import { expect, test } from "@playwright/test";

const token = process.env.LANGAI_E2E_TOKEN;
test.beforeAll(() => {
  if (!token)
    throw new Error(
      "LANGAI_E2E_TOKEN is required for a disposable test deployment",
    );
});

const meanings =
  "river stone moon sun leaf cloud sand bird fish tree wind fire rain hill seed root bark path star water sky soil grass flower creek lake mountain valley ocean island".split(
    " ",
  );

test("upload, review, train, compare, deploy and query the real API", async ({
  page,
  context,
}) => {
  // This test must use the explicitly enabled test encoder; it never fabricates metrics.
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByLabel("Workspace API key").fill(token!);
  await page.getByRole("button", { name: "Connect workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Languages", exact: true }),
  ).toBeVisible();
  const cookie = (await context.cookies()).find(
    (c) => c.name === "langai_session",
  );
  expect(cookie?.httpOnly).toBe(true);
  expect(cookie?.sameSite).toBe("Strict");
  await page
    .getByRole("link", { name: "Create language", exact: true })
    .click();
  const name = `Synthetic browser QA ${Date.now()}`;
  await page
    .getByRole("textbox", { name: "Language name", exact: true })
    .fill(name);
  await page
    .getByRole("textbox", { name: "Description", exact: true })
    .fill("Engineering fixture; no Indigenous vocabulary.");
  await page
    .getByRole("button", { name: "Create language", exact: true })
    .click();
  await expect(page).toHaveURL(/\/languages\/[0-9a-f-]{36}$/);
  const languagePath = new URL(page.url()).pathname;
  const language = languagePath.split("/").pop();
  await page
    .getByRole("navigation", { name: "Language", exact: true })
    .getByRole("link", { name: /^Dictionary/ })
    .click();
  await page
    .getByRole("button", { name: "Upload dictionary", exact: true })
    .click();
  const bytes = Buffer.from(
    "word,definition\n" +
      meanings
        .map(
          (meaning, i) =>
            `synthetic-${i.toString().padStart(3, "0")},${meaning}`,
        )
        .join("\n"),
  );
  await page.locator('input[type="file"]').setInputFiles({
    name: "synthetic-browser.csv",
    mimeType: "text/csv",
    buffer: bytes,
  });
  await page
    .getByRole("textbox", { name: "Owner", exact: true })
    .fill("Fixture author");
  await page
    .getByRole("textbox", { name: "Source / reference", exact: true })
    .fill("Artificial test identifiers");
  await page
    .getByRole("textbox", { name: "Licence / permission terms", exact: true })
    .fill("CC0 test fixture");
  await page
    .getByRole("checkbox", {
      name: "I have permission to use this dictionary for model training.",
    })
    .check();
  await page.getByRole("button", { name: "Upload & map columns" }).click();
  await expect(
    page.getByRole("heading", { name: "Connect your columns" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Preview extraction" }).click();
  await page.getByRole("button", { name: "Accept mappings & import" }).click();
  await expect(
    page.getByRole("heading", { name: "Review the extracted entries" }),
  ).toBeVisible();
  // A clean row can be explicitly excluded and stays excluded after bulk approval.
  const excluded = page.getByRole("row").filter({ hasText: "synthetic-001" });
  await excluded.getByRole("button", { name: "Exclude", exact: true }).click();
  await expect(excluded.getByText("Excluded", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Approve eligible entries" }).click();
  await page.getByRole("link", { name: "Create dataset", exact: true }).click();
  await page.getByRole("checkbox", { name: /^synthetic-browser.csv/ }).check();
  await page
    .getByRole("button", { name: "Create dataset", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Dictionary v1", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Train model", exact: true }).click();
  await page
    .getByRole("textbox", { name: "Base model", exact: true })
    .fill("test-tiny");
  await page
    .getByRole("button", { name: "Start training", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Evaluation results", exact: true }),
  ).toBeVisible({ timeout: 120_000 });
  await expect(
    page.getByRole("cell", { name: "Recall@1", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("navigation", { name: "Language", exact: true })
    .getByRole("link", { name: "Models", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Approve model", exact: true })
    .click();
  await page.getByRole("button", { name: "Deploy", exact: true }).click();
  await expect(
    page.getByText("Available through the private inference API"),
  ).toBeVisible();
  const search = await context.request.post("/api/proxy/v1/search", {
    headers: { Origin: new URL(page.url()).origin },
    data: { language, query: "water" },
  });
  expect(search.status()).toBe(200);
  const result = await search.json();
  expect(result.matches).toHaveLength(10);
  expect(result.score_type).toBe("cosine_similarity");
  await page
    .getByRole("navigation", { name: "Language", exact: true })
    .getByRole("link", { name: "Playground", exact: true })
    .click();
  await page
    .getByRole("textbox", { name: "Search your dictionary" })
    .fill("water");
  await page.getByRole("button", { name: "Run query" }).click();
  await expect(
    page.getByRole("heading", { name: "Results for “water”" }),
  ).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(375);
  expect(errors).toEqual([]);
});

test("session rejects malformed JSON, oversized bodies and cross-origin requests", async ({
  request,
}) => {
  const origin = new URL(process.env.LANGAI_E2E_URL || "http://127.0.0.1:3100")
    .origin;
  const malformed = await request.post("/api/session", {
    headers: { Origin: origin, "Content-Type": "application/json" },
    data: "{",
  });
  expect(malformed.status()).toBe(400);
  const oversized = await request.post("/api/session", {
    headers: { Origin: origin },
    data: { token: "x".repeat(3000) },
  });
  expect(oversized.status()).toBe(413);
  const foreign = await request.post("/api/session", {
    headers: { Origin: "https://untrusted.invalid" },
    data: { token },
  });
  expect(foreign.status()).toBe(403);
  const anonymous = await request.get("/api/proxy/languages");
  expect(anonymous.status()).toBe(401);
});
