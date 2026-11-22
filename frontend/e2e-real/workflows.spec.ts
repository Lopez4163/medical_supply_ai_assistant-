import { expect, test, type Page } from "@playwright/test";

async function sendChat(page: Page, text: string): Promise<void> {
  const composer = page.getByLabel("Message the AI Supply Assistant");
  await composer.fill(text);
  await composer.press("Enter");
}

async function addDraftLineThroughMockChat(page: Page): Promise<void> {
  await sendChat(page, "add 2 PPE-NIT-M");
  await expect(page.getByRole("button", { name: "Quotation (1)" })).toBeVisible();
}

async function fillQuoteReview(page: Page): Promise<void> {
  await page.getByLabel("First name").fill("Ada");
  await page.getByLabel("Last name").fill("Lovelace");
  await page.getByLabel("Email").fill("ada@example.test");
  await page.getByLabel("Delivery city").fill("Cali");
}

async function openQuoteConfirmation(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Quotation (1)" }).click();
  await page.getByRole("button", { name: "Review quotation" }).click();
  await fillQuoteReview(page);
  await page.getByRole("button", { name: "Review quotation" }).click();
  await expect(page.getByRole("heading", { name: "Review quotation" })).toBeVisible();
  await page.getByLabel("I confirm this synthetic quotation inquiry.").check();
}

test("uses real FastAPI cookies, Origin validation, mock search pagination, and restoration", async ({
  context,
  page,
}) => {
  const bootstrap = page.waitForResponse(
    (response) => response.url().endsWith("/api/v1/sessions") && response.request().method() === "POST",
  );
  await page.goto("/");
  const bootstrapResponse = await bootstrap;
  expect(bootstrapResponse.status()).toBe(201);
  expect(bootstrapResponse.headers()["access-control-allow-origin"]).toBe("http://localhost:3101");
  expect(bootstrapResponse.headers()["access-control-allow-credentials"]).toBe("true");
  expect(await context.cookies("http://localhost:8100")).toContainEqual(
    expect.objectContaining({ name: "bmh_guest", httpOnly: true }),
  );

  await sendChat(page, "find PPE");
  await expect(page.getByText(/matching synthetic catalog items/i)).toBeVisible();
  await expect(page.getByRole("button", { name: "Show more products" })).toBeVisible();
  await page.getByRole("button", { name: "Show more products" }).click();
  await expect(page.getByText("show more", { exact: true })).toBeVisible();

  await page.reload();
  await expect(page.getByText("show more", { exact: true })).toBeVisible();
});

test("creates, updates, removes, reviews, and submits a real draft", async ({ page }) => {
  await page.goto("/");
  await addDraftLineThroughMockChat(page);

  await page.getByRole("button", { name: "Quotation (1)" }).click();
  const quantity = page.getByRole("spinbutton", { name: "Quantity" });
  await quantity.fill("3");
  await page.getByRole("button", { name: "Update" }).click();
  await expect(quantity).toHaveValue("3");
  await page.getByRole("button", { name: "Remove" }).click();
  await expect(page.getByRole("button", { name: "Quotation (0)" })).toBeVisible();

  await page.getByRole("button", { name: "Close" }).click();
  await addDraftLineThroughMockChat(page);
  await openQuoteConfirmation(page);
  await page.getByRole("button", { name: "Confirm quotation inquiry" }).click();

  await expect(page.getByLabel("Quotation submitted")).toBeVisible();
  await expect(page.getByRole("button", { name: "Quotation (0)" })).toBeVisible();
  await expect(page.getByText(/does not create an order/i)).toBeVisible();
});

test("submits a real support inquiry after explicit opt-in and confirmation", async ({ page }) => {
  await page.goto("/");
  await sendChat(page, "support");
  await page.getByRole("button", { name: "Start support inquiry" }).click();
  await page.getByLabel("I want to create a synthetic support inquiry.").check();
  await page.getByLabel("First name").fill("Ada");
  await page.getByLabel("Last name").fill("Lovelace");
  await page.getByLabel("Email").fill("ada@example.test");
  await page.getByLabel("Subject").fill("Delivery question");
  await page.getByLabel("Summary").fill("Please review delivery options.");
  await page.getByRole("button", { name: "Review inquiry" }).click();
  await page.getByLabel("I confirm this synthetic support inquiry.").check();
  await page.getByRole("button", { name: "Confirm support inquiry" }).click();

  await expect(page.getByLabel("Support inquiry submitted")).toBeVisible();
  await expect(page.getByText(/does not notify real staff/i)).toBeVisible();
});

test("isolates drafts across separate real guest sessions", async ({ browser }) => {
  const guestA = await browser.newContext();
  const guestAPage = await guestA.newPage();
  await guestAPage.goto("/");
  await addDraftLineThroughMockChat(guestAPage);

  const guestB = await browser.newContext();
  const guestBPage = await guestB.newPage();
  await guestBPage.goto("/");
  await expect(guestBPage.getByRole("button", { name: "Quotation (0)" })).toBeVisible();
  await expect(guestBPage.getByText(/I added the requested item/i)).toHaveCount(0);

  await guestA.close();
  await guestB.close();
});

test("reconciles a lost real quote-submission response without issuing a duplicate submit", async ({
  page,
}) => {
  await page.goto("/");
  await addDraftLineThroughMockChat(page);
  await openQuoteConfirmation(page);

  let backendSubmitRequests = 0;
  await page.route("http://localhost:8100/api/v1/quotations/submissions", async (route) => {
    backendSubmitRequests += 1;
    await route.fetch();
    await route.abort();
  });
  await page.getByRole("button", { name: "Confirm quotation inquiry" }).click();
  await expect(page.getByRole("button", { name: "Check submission status" })).toBeVisible();
  await page.getByRole("button", { name: "Check submission status" }).click();

  await expect(page.getByLabel("Quotation submitted")).toBeVisible();
  expect(backendSubmitRequests).toBe(1);
  await expect(page.getByRole("button", { name: "Quotation (0)" })).toBeVisible();
});
