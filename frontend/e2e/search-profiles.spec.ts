import { expect, test } from "@playwright/test";

test("creates and reviews a Search Profile without running collectors", async ({ page }) => {
  let profileCreated = false;
  const profile = {
    id: "e2e-profile",
    name: "Controlled E2E profile",
    description: null,
    enabled: false,
    target_roles: ["Mechanical Engineer"],
    role_aliases: [],
    include_keywords: [],
    exclude_keywords: [],
    skills_priority: [],
    locations: [],
    countries: [],
    location_types: [],
    remote_scope: "unknown",
    remote_eligibility: "unknown",
    salary_min: null,
    salary_currency: null,
    seniority_levels: [],
    employment_types: [],
    sources: ["manual"],
    freshness_days: null,
    scoring_weights: {},
    created_at: "2026-09-18T00:00:00+00:00",
    updated_at: "2026-09-18T00:00:00+00:00",
    last_run_at: null,
  };
  await page.route("**/api/search-profiles/capabilities", (route) =>
    route.fulfill({
      json: {
        sources: [{ id: "manual", available: true, enabled: true, reason: null }],
        location_types: ["remote", "unknown"],
        remote_scopes: ["brazil", "unknown"],
        remote_eligibilities: ["eligible", "unknown"],
        employment_types: ["fulltime"],
      },
    }),
  );
  await page.route(/\/api\/search-profiles(\/|$|\?)/, async (route) => {
    const request = route.request();
    if (request.url().includes("/capabilities")) {
      await route.fulfill({
        json: {
          sources: [{ id: "manual", available: true, enabled: true, reason: null }],
          location_types: ["remote", "unknown"],
          remote_scopes: ["brazil", "unknown"],
          remote_eligibilities: ["eligible", "unknown"],
          employment_types: ["fulltime"],
        },
      });
      return;
    }
    if (request.url().includes("/run")) {
      await route.fulfill({
        json: {
          id: "e2e-run",
          search_profile_id: "e2e-profile",
          status: "completed",
          started_at: "2026-09-18T00:00:00+00:00",
          finished_at: "2026-09-18T00:00:01+00:00",
          sources: ["manual"],
          queries: ["Mechanical Engineer"],
          jobs_found: 1,
          jobs_new: 1,
          jobs_matched: 0,
          errors: [],
          duration_seconds: 1,
        },
      });
      return;
    }
    if (request.method() === "POST") {
      profileCreated = true;
      await route.fulfill({ status: 201, json: profile });
      return;
    }
    if (request.url().endsWith("/e2e-profile")) {
      await route.fulfill({ json: profile });
      return;
    }
    if (request.url().includes("/matches")) {
      await route.fulfill({ json: { items: [], total: 0, limit: 10, offset: 0 } });
      return;
    }
    if (request.url().includes("/runs")) {
      await route.fulfill({ json: { items: [], total: 0, limit: 10, offset: 0 } });
      return;
    }
    await route.fulfill({
      json: {
        items: profileCreated ? [profile] : [],
        total: profileCreated ? 1 : 0,
        limit: 50,
        offset: 0,
      },
    });
  });
  await page.goto("/?view=search-profiles");
  await expect(page.getByText("Você ainda não criou uma estratégia de busca.")).toBeVisible();
  await page.getByRole("button", { name: /Create first Search Profile/i }).click();
  await page.getByLabel("Name").fill("Controlled E2E profile");
  await page.getByRole("button", { name: "Create Search Profile" }).click();
  await expect(page.getByRole("heading", { name: "Controlled E2E profile" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Execute search/i })).toBeDisabled();
});
