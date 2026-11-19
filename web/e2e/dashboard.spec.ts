import AxeBuilder from "@axe-core/playwright";
import { type Page, expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
});

async function noViolations(page: Page) {
  await page.waitForLoadState("networkidle");
  const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(r.violations.map((v) => `${v.id}: ${v.nodes.length}`)).toEqual([]);
}

test("results compare every design on the same traffic", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("platform-lost")).toBeVisible();
  const dev = page.getByRole("region", { name: "Development shops" });
  await expect(dev.getByRole("rowheader", { name: "Platform", exact: true })).toBeVisible();
  await expect(dev.getByRole("rowheader", { name: "Shop as found" })).toBeVisible();
  await expect(dev.locator("tbody tr")).toHaveCount(15);
  await noViolations(page);
});

test("Black Friday switches metric and reads values on hover", async ({ page }) => {
  await page.goto("/#/blackfriday");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Black Friday, minute by minute");
  await page.getByRole("button", { name: "Served from the cache" }).click();
  await expect(page.getByRole("button", { name: "Served from the cache" })).toHaveAttribute("aria-pressed", "true");
  const chart = page.getByRole("img", { name: /Served from the cache on Black Friday/ });
  const box = (await chart.boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.4, box.y + box.height * 0.5);
  await expect(page.locator("figcaption")).toContainText("Platform:");
  await noViolations(page);
});

test("releases and alerts show the gates and the held-out verdict", async ({ page }) => {
  await page.goto("/#/releases");
  const dev = page.getByRole("region", { name: "Development shops" });
  await expect(dev.getByRole("columnheader", { name: "Stopped by SonarQube" })).toBeVisible();
  await expect(page.getByText("Gate not passed")).toBeVisible();
  await expect(page.getByText(/detected 0 of 5 episodes/)).toBeVisible();
  await noViolations(page);
});

test("an API failure offers a retry", async ({ page }) => {
  await page.route("**/api/results", (r) => r.fulfill({ status: 503, body: JSON.stringify({ detail: "warming up" }) }));
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("warming up");
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
});
