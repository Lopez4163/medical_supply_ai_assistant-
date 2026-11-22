import { expect, test, type Page, type Route } from "@playwright/test";

const guestA = "31dced59-7efc-4b51-8c8a-2e8a1c2f34f9";
const guestB = "5600df46-1be9-4f08-9eb9-c4c0496b3b63";

type MockOptions = {
  conversationId: string;
  includeSupport?: boolean;
  includePagination?: boolean;
};

type Draft = {
  created_at: string;
  id: string;
  indicative_total_usd: string;
  lines: Array<{
    availability: string;
    availability_notice: string;
    created_at: string;
    id: string;
    indicative_line_subtotal_usd: string;
    indicative_unit_price_usd: string;
    product_id: string;
    product_name: string;
    quantity_sufficient: boolean;
    requested_quantity: number;
    sales_unit: string;
    selector_attributes: Record<string, string>;
    sku: string;
    updated_at: string;
  }>;
  status: string;
  updated_at: string;
  version: number;
};

function json(route: Route, body: unknown, status = 200): Promise<void> {
  return route.fulfill({
    body: JSON.stringify(body),
    contentType: "application/json",
    status,
  });
}

function product(sku = "PPE-NIT-M", name = "Nitrile Gloves") {
  return {
    availability: "in_stock",
    category_code: "PPE",
    category_name: "Personal protective equipment",
    image_fallback_key: "PPE fallback",
    indicative_price_usd: "12.00",
    lifecycle_status: "active",
    name,
    primary_image_reference: null,
    product_id: sku === "PPE-NIT-M" ? "gloves" : "masks",
    sales_unit: "Box of 100",
    selector_attributes: { size: "Medium" },
    sku,
  };
}

function createDraft(): Draft {
  return {
    created_at: "2026-11-22T12:00:00Z",
    id: "c84d9f32-1b01-4c8b-b56f-a38b46e1c60d",
    indicative_total_usd: "24.00",
    lines: [
      {
        availability: "in_stock",
        availability_notice: "Available.",
        created_at: "2026-11-22T12:00:00Z",
        id: "9dc44386-ff7b-4c47-9779-15d13e5b3b0a",
        indicative_line_subtotal_usd: "24.00",
        indicative_unit_price_usd: "12.00",
        product_id: "gloves",
        product_name: "Nitrile Gloves",
        quantity_sufficient: true,
        requested_quantity: 2,
        sales_unit: "Box of 100",
        selector_attributes: { size: "Medium" },
        sku: "PPE-NIT-M",
        updated_at: "2026-11-22T12:00:00Z",
      },
    ],
    status: "active",
    updated_at: "2026-11-22T12:00:00Z",
    version: 1,
  };
}

function conversation(options: MockOptions) {
  return {
    conversation_id: options.conversationId,
    messages: [
      {
        created_at: "2026-11-22T12:00:00Z",
        elements: [
          {
            kind: "product_results",
            result_context: "search",
            result_set: {
              next_cursor: options.includePagination ? "opaque-page-two" : null,
              products: [product()],
            },
          },
          ...(options.includeSupport
            ? [
                {
                  form: {
                    description: "We can prepare a synthetic inquiry.",
                    title: "Need support?",
                  },
                  kind: "support_inquiry_form",
                },
              ]
            : []),
        ],
        freshness: "historical_snapshot",
        id: `welcome-${options.conversationId}`,
        kind: "welcome",
        ordinal: 0,
        role: "assistant",
        text: `Welcome ${options.conversationId === guestA ? "guest A" : "guest B"}.`,
      },
    ],
  };
}

async function installMockApi(page: Page, options: MockOptions): Promise<void> {
  let draft: Draft | null = null;
  let quoteSubmitted = false;
  await page.route("http://localhost:8000/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path.endsWith("/sessions")) {
      await json(route, {
        conversation_id: options.conversationId,
        expires_at: "2026-11-29T12:00:00Z",
        restored: true,
        welcome_message: "Welcome.",
      });
      return;
    }
    if (path.endsWith("/conversations/current")) {
      await json(route, conversation(options));
      return;
    }
    if (path.endsWith("/quotations/draft") && request.method() === "GET") {
      await json(route, { draft: quoteSubmitted ? null : draft });
      return;
    }
    if (path.endsWith("/products/PPE-NIT-M")) {
      await json(route, {
        ...product(),
        description: "Synthetic product details.",
        searchable_attributes: {},
      });
      return;
    }
    if (path.endsWith("/quotations/draft/lines") && request.method() === "POST") {
      draft = createDraft();
      await json(route, draft);
      return;
    }
    if (path.endsWith("/quotations/draft/review")) {
      await json(route, {
        disclosure: "This is a synthetic quotation inquiry.",
        draft,
        expires_at: "2026-11-22T13:00:00Z",
        review_token: "x".repeat(24),
      });
      return;
    }
    if (path.endsWith("/quotations/submissions")) {
      quoteSubmitted = true;
      await json(
        route,
        {
          message: "The synthetic quotation inquiry was recorded.",
          reference: "Q-20261122-001",
          submitted_at: "2026-11-22T12:15:00Z",
        },
        201,
      );
      return;
    }
    if (path.endsWith("/support/review")) {
      await json(route, {
        disclosure: "This is a synthetic support inquiry.",
        expires_at: "2026-11-22T13:00:00Z",
        review_token: "y".repeat(24),
        subject: "Delivery question",
        summary: "Please review delivery options.",
      });
      return;
    }
    if (path.endsWith("/support/inquiries")) {
      await json(
        route,
        {
          message: "The synthetic support inquiry was recorded.",
          reference: "S-20261122-001",
          submitted_at: "2026-11-22T12:15:00Z",
        },
        201,
      );
      return;
    }
    if (path.endsWith("/chat/messages")) {
      const payload = request.postDataJSON() as { cursor?: string; text: string };
      await json(route, {
        assistant_message: {
          created_at: "2026-11-22T12:01:00Z",
          elements: [
            {
              kind: "product_results",
              result_context: "search",
              result_set: {
                next_cursor: null,
                products: [product("PPE-MASK-M", "Surgical Masks")],
              },
            },
          ],
          freshness: "current",
          id: "assistant-page-two",
          kind: "assistant",
          ordinal: 2,
          role: "assistant",
          text: payload.cursor ? "Additional matching products." : "Mock response.",
        },
        conversation_id: options.conversationId,
        draft_changed: false,
        user_message: {
          created_at: "2026-11-22T12:01:00Z",
          elements: [],
          freshness: "current",
          id: "user-page-two",
          kind: "user",
          ordinal: 1,
          role: "user",
          text: payload.text,
        },
      });
      return;
    }
    await json(route, { error: { code: "NOT_FOUND", message: "Not found" } }, 404);
  });
}

test("completes a synthetic quotation journey and clears the draft indicator", async ({ page }) => {
  await installMockApi(page, { conversationId: guestA });
  await page.goto("/");

  await page.getByRole("button", { name: "View details for PPE-NIT-M" }).click();
  await page.getByLabel("Quantity for PPE-NIT-M").fill("2");
  await page.getByRole("button", { name: "Add to quote" }).click();
  await expect(page.getByRole("button", { name: "Quotation (1)" })).toBeVisible();

  await page.getByRole("button", { name: "Quotation (1)" }).click();
  await page.getByRole("button", { name: "Review quotation" }).click();
  await page.getByLabel("First name").fill("Ada");
  await page.getByLabel("Last name").fill("Lovelace");
  await page.getByLabel("Email").fill("ada@example.test");
  await page.getByLabel("Delivery city").fill("Cali");
  await page.getByRole("button", { name: "Review quotation" }).click();
  await page.getByLabel("I confirm this synthetic quotation inquiry.").check();
  await page.getByRole("button", { name: "Confirm quotation inquiry" }).click();

  await expect(page.getByText("Reference: Q-20261122-001")).toBeVisible();
  await expect(page.getByRole("button", { name: "Quotation (0)" })).toBeVisible();
  await expect(page.getByText(/does not create an order/i)).toBeVisible();
});

test("completes a synthetic support journey with explicit opt-in", async ({ page }) => {
  await installMockApi(page, { conversationId: guestA, includeSupport: true });
  await page.goto("/");

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

  await expect(page.getByText("Reference: S-20261122-001")).toBeVisible();
  await expect(page.getByText(/does not notify real staff/i)).toBeVisible();
});

test("restores a conversation, appends a paged batch, and keeps guest histories isolated", async ({
  browser,
}) => {
  const guestAContext = await browser.newContext();
  const guestAPage = await guestAContext.newPage();
  await installMockApi(guestAPage, { conversationId: guestA, includePagination: true });
  await guestAPage.goto("/");

  await expect(guestAPage.getByText("Welcome guest A.")).toBeVisible();
  await guestAPage.reload();
  await expect(guestAPage.getByText("Welcome guest A.")).toBeVisible();
  await guestAPage.getByRole("button", { name: "Show more products" }).click();
  await expect(guestAPage.getByText("Additional matching products.")).toBeVisible();
  await expect(guestAPage.getByText("Surgical Masks")).toBeVisible();

  const guestBContext = await browser.newContext();
  const guestBPage = await guestBContext.newPage();
  await installMockApi(guestBPage, { conversationId: guestB });
  await guestBPage.goto("/");
  await expect(guestBPage.getByText("Welcome guest B.")).toBeVisible();
  await expect(guestBPage.getByText("Welcome guest A.")).toHaveCount(0);

  await guestAContext.close();
  await guestBContext.close();
});

test("keeps the quotation drawer keyboard-operable on a narrow viewport", async ({ page }) => {
  await page.setViewportSize({ height: 844, width: 390 });
  await installMockApi(page, { conversationId: guestA });
  await page.goto("/");

  const trigger = page.getByRole("button", { name: "Quotation (0)" });
  await trigger.press("Enter");
  const drawer = page.getByRole("dialog", { name: "Draft quotation" });
  await expect(drawer).toBeVisible();
  await expect(page.getByRole("button", { name: "Close" })).toBeFocused();
  const bounds = await drawer.boundingBox();
  expect(Math.round(bounds?.width ?? 0)).toBe(390);

  await page.keyboard.press("Escape");
  await expect(drawer).toHaveCount(0);
  await expect(trigger).toBeFocused();
});

test("renders an expired-session state without enabling the composer", async ({ page }) => {
  await page.route("http://localhost:8000/api/v1/**", async (route) => {
    if (new URL(route.request().url()).pathname.endsWith("/sessions")) {
      await json(route, { error: { code: "SESSION_EXPIRED", message: "Expired" } }, 401);
      return;
    }
    await json(route, { error: { code: "NOT_FOUND", message: "Not found" } }, 404);
  });
  await page.goto("/");

  await expect(page.getByText("Your guest session expired.")).toBeVisible();
  await expect(page.getByLabel("Message the AI Supply Assistant")).toBeDisabled();
  await expect(page.getByRole("button", { name: "Send" })).toBeDisabled();
});
