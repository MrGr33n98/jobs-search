import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SearchProfilesView } from "./SearchProfilesView";
import { mockApi } from "../../test/mockApi";
import { renderWithProviders } from "../../test/render";

const capabilities = {
  sources: [{ id: "manual", available: true, enabled: true, reason: null }],
  location_types: ["remote", "unknown"],
  remote_scopes: ["brazil", "unknown"],
  remote_eligibilities: ["eligible", "unknown"],
  employment_types: ["fulltime"],
};

const profile = {
  id: "profile-1",
  name: "Mechanical search",
  description: null,
  enabled: true,
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

function routes(items: (typeof profile)[] = []) {
  return [
    {
      path: "/api/search-profiles",
      reply: () => ({ items, total: items.length, limit: 50, offset: 0 }),
    },
    { path: "/api/search-profiles/capabilities", reply: () => capabilities },
  ];
}

describe("SearchProfilesView", () => {
  it("shows the honest empty state and opens the progressive form", async () => {
    mockApi(routes());
    renderWithProviders(<SearchProfilesView />);
    expect(
      await screen.findByText("Você ainda não criou uma estratégia de busca."),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Create first Search Profile/i }));
    expect(await screen.findByRole("heading", { name: "New Search Profile" })).toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toBeInTheDocument();
  });

  it("creates a profile with backend capabilities only", async () => {
    mockApi([
      { method: "POST", path: "/api/search-profiles", reply: () => profile, status: 201 },
      ...routes(),
    ]);
    renderWithProviders(<SearchProfilesView />);
    fireEvent.click(await screen.findByRole("button", { name: /Create first Search Profile/i }));
    fireEvent.change(await screen.findByLabelText("Name"), {
      target: { value: "Mechanical search" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create Search Profile" }));
    await waitFor(() => expect(window.location.search).toContain("profile=profile-1"));
    expect(screen.queryByText("Greenhouse")).not.toBeInTheDocument();
  });

  it("renders profile details with empty matches and runs", async () => {
    mockApi([
      ...routes([profile]),
      { path: "/api/search-profiles/profile-1", reply: () => profile },
      {
        path: "/api/search-profiles/profile-1/matches",
        reply: () => ({ items: [], total: 0, limit: 10, offset: 0 }),
      },
      {
        path: "/api/search-profiles/profile-1/runs",
        reply: () => ({ items: [], total: 0, limit: 10, offset: 0 }),
      },
    ]);
    window.history.replaceState(null, "", "?view=search-profiles&profile=profile-1");
    renderWithProviders(<SearchProfilesView />);
    expect(await screen.findByRole("heading", { name: "Mechanical search" })).toBeInTheDocument();
    expect(
      await screen.findByText("Nenhuma vaga compatível foi encontrada para este perfil."),
    ).toBeInTheDocument();
    expect(
      await screen.findByText("Nenhuma busca foi executada para este perfil."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Execute search/i })).toBeEnabled();
  });
});
