import { useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { ArrowLeft, ChevronLeft, ChevronRight, Edit3, Pause, Play, Plus, Save } from "lucide-react";

import { api } from "../../api/client";
import type {
  SearchProfile,
  SearchProfileCapabilities,
  SearchProfilePayload,
} from "../../api/types";
import { useConfirm } from "../../app/confirmContext";
import { setParams, useRoute } from "../../app/router";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { EmptyState, ErrorNotice, Skeleton, Spinner } from "../../components/EmptyState";
import { Checkbox, Field, Input, Select, Textarea } from "../../components/Field";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { formatDateTime } from "../shared/format";
import {
  keys,
  useSearchProfile,
  useSearchProfileCapabilities,
  useSearchProfileMatches,
  useSearchProfileRuns,
  useSearchProfiles,
} from "../shared/queries";

type FormState = SearchProfilePayload;
const EMPTY_FORM: FormState = {
  name: "",
  description: "",
  enabled: false,
  target_roles: [],
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
  sources: [],
  freshness_days: null,
};

function humanize(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function profileForm(profile: SearchProfile | undefined): FormState {
  if (!profile) return { ...EMPTY_FORM };
  return {
    name: profile.name,
    description: profile.description ?? "",
    enabled: profile.enabled,
    target_roles: profile.target_roles,
    role_aliases: profile.role_aliases,
    include_keywords: profile.include_keywords,
    exclude_keywords: profile.exclude_keywords,
    skills_priority: profile.skills_priority,
    locations: profile.locations,
    countries: profile.countries,
    location_types: profile.location_types,
    remote_scope: profile.remote_scope,
    remote_eligibility: profile.remote_eligibility,
    salary_min: profile.salary_min,
    salary_currency: profile.salary_currency,
    seniority_levels: profile.seniority_levels,
    employment_types: profile.employment_types,
    sources: profile.sources,
    freshness_days: profile.freshness_days,
  };
}

function TagEditor({
  label,
  values,
  onChange,
  placeholder,
}: {
  label: string;
  values: string[];
  onChange: (values: string[]) => void;
  placeholder: string;
}) {
  const [value, setValue] = useState("");
  const add = () => {
    const clean = value.trim();
    if (clean && !values.some((item) => item.toLowerCase() === clean.toLowerCase()))
      onChange([...values, clean]);
    setValue("");
  };
  return (
    <Field label={label}>
      <div className="flex gap-2">
        <Input
          value={value}
          placeholder={placeholder}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              add();
            }
          }}
        />
        <Button type="button" size="sm" onClick={add} aria-label={`Add ${label}`}>
          <Plus size={14} aria-hidden="true" />
        </Button>
      </div>
      {values.length ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {values.map((item) => (
            <Badge key={item}>
              <button
                type="button"
                aria-label={`Remove ${item}`}
                onClick={() => onChange(values.filter((entry) => entry !== item))}
              >
                {item} ×
              </button>
            </Badge>
          ))}
        </div>
      ) : (
        <p className="mt-1 text-xs text-fg-faint">None configured.</p>
      )}
    </Field>
  );
}

function MultiSelect({
  label,
  values,
  options,
  onChange,
  hint,
}: {
  label: string;
  values: string[];
  options: string[];
  onChange: (values: string[]) => void;
  hint?: string;
}) {
  return (
    <Field label={label} hint={hint}>
      <div className="flex flex-wrap gap-x-4 gap-y-2">
        {options.map((option) => (
          <Checkbox
            key={option}
            label={humanize(option)}
            checked={values.includes(option)}
            onChange={(event) =>
              onChange(
                event.target.checked
                  ? [...values, option]
                  : values.filter((value) => value !== option),
              )
            }
          />
        ))}
      </div>
    </Field>
  );
}

function ProfileForm({
  profile,
  capabilities,
  onDone,
  onCancel,
}: {
  profile?: SearchProfile;
  capabilities?: SearchProfileCapabilities;
  onDone: (saved: SearchProfile) => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState(() => profileForm(profile));
  const [error, setError] = useState<unknown>(null);
  const [saving, setSaving] = useState(false);
  const dirty =
    form.name !== (profile?.name ?? "") ||
    JSON.stringify(form) !== JSON.stringify(profileForm(profile));
  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((current) => ({ ...current, [key]: value }));
  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (!form.name.trim()) {
      setError(new Error("Name is required."));
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const payload = {
        ...form,
        name: form.name.trim(),
        description: form.description?.trim() || null,
      };
      const saved = profile
        ? await api.updateSearchProfile(profile.id, payload)
        : await api.createSearchProfile(payload);
      onDone(saved);
    } catch (cause) {
      setError(cause);
    } finally {
      setSaving(false);
    }
  };
  const options = capabilities;
  return (
    <form onSubmit={save} className="flex flex-col gap-4">
      {error ? <ErrorNotice error={error} /> : null}
      <Card title="Identity">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Name" htmlFor="profile-name">
            <Input
              id="profile-name"
              required
              autoFocus
              value={form.name}
              onChange={(event) => set("name", event.target.value)}
              placeholder="A strategy name"
            />
          </Field>
          <Field label="Description" htmlFor="profile-description">
            <Textarea
              id="profile-description"
              value={form.description ?? ""}
              onChange={(event) => set("description", event.target.value)}
              placeholder="Optional context for this search"
            />
          </Field>
        </div>
        <div className="mt-3">
          <Checkbox
            label="Active"
            checked={form.enabled}
            onChange={(event) => set("enabled", event.target.checked)}
          />
        </div>
      </Card>
      <Card title="What to look for">
        <div className="grid gap-4 lg:grid-cols-2">
          <TagEditor
            label="Target roles"
            values={form.target_roles}
            onChange={(value) => set("target_roles", value)}
            placeholder="Add a target role"
          />
          <TagEditor
            label="Role aliases"
            values={form.role_aliases}
            onChange={(value) => set("role_aliases", value)}
            placeholder="Add an alias"
          />
          <TagEditor
            label="Include keywords"
            values={form.include_keywords}
            onChange={(value) => set("include_keywords", value)}
            placeholder="Terms to include"
          />
          <TagEditor
            label="Exclude keywords"
            values={form.exclude_keywords}
            onChange={(value) => set("exclude_keywords", value)}
            placeholder="Terms to exclude"
          />
        </div>
      </Card>
      <Card title="Location">
        <div className="grid gap-4 lg:grid-cols-2">
          <TagEditor
            label="Locations"
            values={form.locations}
            onChange={(value) => set("locations", value)}
            placeholder="City or region"
          />
          <TagEditor
            label="Countries"
            values={form.countries}
            onChange={(value) => set("countries", value)}
            placeholder="Country"
          />
          {options ? (
            <MultiSelect
              label="Location type"
              values={form.location_types}
              options={options.location_types}
              onChange={(value) => set("location_types", value)}
            />
          ) : null}
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Remote scope">
              <Select
                value={form.remote_scope}
                onChange={(event) => set("remote_scope", event.target.value)}
              >
                {(options?.remote_scopes ?? ["unknown"]).map((item) => (
                  <option key={item} value={item}>
                    {humanize(item)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Remote eligibility">
              <Select
                value={form.remote_eligibility}
                onChange={(event) => set("remote_eligibility", event.target.value)}
              >
                {(options?.remote_eligibilities ?? ["unknown"]).map((item) => (
                  <option key={item} value={item}>
                    {humanize(item)}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
        </div>
      </Card>
      <Card title="Filters and sources">
        <div className="grid gap-4 lg:grid-cols-2">
          <MultiSelect
            label="Employment types"
            values={form.employment_types}
            options={options?.employment_types ?? []}
            onChange={(value) => set("employment_types", value)}
          />
          <Field label="Freshness (days)" hint="Leave empty to keep the backend default.">
            <Input
              type="number"
              min="1"
              value={form.freshness_days ?? ""}
              onChange={(event) =>
                set("freshness_days", event.target.value ? Number(event.target.value) : null)
              }
            />
          </Field>
          <Field
            label="Sources"
            hint="Only sources exposed as available and enabled by the backend can be selected."
          >
            <div className="flex flex-wrap gap-x-4 gap-y-2">
              {(options?.sources ?? [])
                .filter((source) => source.available && source.enabled)
                .map((source) => (
                  <Checkbox
                    key={source.id}
                    label={source.id}
                    checked={form.sources.includes(source.id)}
                    onChange={(event) =>
                      set(
                        "sources",
                        event.target.checked
                          ? [...form.sources, source.id]
                          : form.sources.filter((value) => value !== source.id),
                      )
                    }
                  />
                ))}
            </div>
          </Field>
        </div>
      </Card>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs text-fg-faint">{dirty ? "Unsaved changes" : "Ready"}</span>
        <div className="flex gap-2">
          <Button type="button" onClick={onCancel} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={saving || !form.name.trim()}>
            <Save size={14} aria-hidden="true" />
            {saving ? "Saving…" : profile ? "Save changes" : "Create Search Profile"}
          </Button>
        </div>
      </div>
    </form>
  );
}

function Pager({
  offset,
  total,
  limit,
  onChange,
}: {
  offset: number;
  total: number;
  limit: number;
  onChange: (offset: number) => void;
}) {
  if (total <= limit) return null;
  return (
    <div className="flex items-center justify-between border-t border-edge pt-2 text-xs text-fg-muted">
      <span>
        {offset + 1}–{Math.min(offset + limit, total)} of {total}
      </span>
      <span className="flex gap-1">
        <Button
          size="sm"
          onClick={() => onChange(Math.max(0, offset - limit))}
          disabled={offset === 0}
          aria-label="Previous page"
        >
          <ChevronLeft size={14} />
        </Button>
        <Button
          size="sm"
          onClick={() => onChange(offset + limit)}
          disabled={offset + limit >= total}
          aria-label="Next page"
        >
          <ChevronRight size={14} />
        </Button>
      </span>
    </div>
  );
}

function ProfileDetails({ profile }: { profile: SearchProfile }) {
  const [matchesOffset, setMatchesOffset] = useState(0);
  const [runsOffset, setRunsOffset] = useState(0);
  const matches = useSearchProfileMatches(profile.id, { limit: 10, offset: matchesOffset });
  const runs = useSearchProfileRuns(profile.id, { limit: 10, offset: runsOffset });
  const client = useQueryClient();
  const run = useMutation({
    mutationFn: () => api.runSearchProfile(profile.id),
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: keys.searchProfileRuns(profile.id, {}) }),
        client.invalidateQueries({ queryKey: ["search-profile-runs", profile.id] }),
        client.invalidateQueries({ queryKey: keys.searchProfile(profile.id) }),
      ]);
    },
  });
  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold">{profile.name}</h2>
            <Badge tone={profile.enabled ? "positive" : "muted"}>
              {profile.enabled ? "Active" : "Inactive"}
            </Badge>
          </div>
          <p className="text-sm text-fg-muted">{profile.description || "No description."}</p>
        </div>
        <Button
          size="sm"
          variant="primary"
          onClick={() => run.mutate()}
          disabled={!profile.enabled || run.isPending}
        >
          <Play size={14} aria-hidden="true" /> {run.isPending ? "Running…" : "Execute search"}
        </Button>
      </header>
      {run.error ? <ErrorNotice error={run.error} /> : null}
      {!profile.enabled ? (
        <p className="text-xs text-fg-faint">Activate this profile before executing a search.</p>
      ) : null}
      {run.data ? (
        <p className="text-xs text-fg-faint">Last execution: {humanize(run.data.status)}.</p>
      ) : null}
      <Card title="Configuration">
        <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
          <Detail
            label="Target roles"
            value={profile.target_roles.concat(profile.role_aliases).join(", ") || "Not configured"}
          />
          <Detail
            label="Keywords"
            value={
              profile.include_keywords.length
                ? `Include: ${profile.include_keywords.join(", ")}`
                : "None configured"
            }
          />
          <Detail
            label="Excluded"
            value={profile.exclude_keywords.join(", ") || "None configured"}
          />
          <Detail
            label="Location"
            value={profile.locations.concat(profile.countries).join(", ") || "Not configured"}
          />
          <Detail
            label="Remote"
            value={`${profile.remote_scope} · ${profile.remote_eligibility}`}
          />
          <Detail label="Sources" value={profile.sources.join(", ") || "None configured"} />
        </dl>
      </Card>
      <Card title="Matches">
        <ResourceState
          query={matches}
          empty="Nenhuma vaga compatível foi encontrada para este perfil."
        >
          <ul className="divide-y divide-edge">
            {matches.data?.items.map((item) => (
              <li
                key={item.match.id}
                className="flex flex-wrap items-center justify-between gap-2 py-2"
              >
                <div>
                  <p className="font-medium">{item.job.title}</p>
                  <p className="text-xs text-fg-muted">
                    {item.job.company} · {item.job.location || "Location unknown"}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone="accent">{Math.round(item.match.score)} score</Badge>
                  <Badge>{item.match.eligibility}</Badge>
                </div>
                {item.match.match_reasons.length ? (
                  <ul className="mt-1 text-xs text-fg-muted">
                    {item.match.match_reasons.slice(0, 3).map((reason) => (
                      <li key={reason}>✓ {reason}</li>
                    ))}
                  </ul>
                ) : null}
              </li>
            ))}
          </ul>
          <Pager {...matches.data!} onChange={setMatchesOffset} />
        </ResourceState>
      </Card>
      <Card title="Runs">
        <ResourceState query={runs} empty="Nenhuma busca foi executada para este perfil.">
          <ul className="divide-y divide-edge">
            {runs.data?.items.map((run) => (
              <li key={run.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <div>
                  <Badge>{run.status}</Badge>
                  <span className="ml-2 text-xs text-fg-muted">
                    {run.started_at ? formatDateTime(run.started_at) : "Not started"}
                  </span>
                </div>
                <span className="text-xs text-fg-muted">{run.jobs_matched} matched</span>
              </li>
            ))}
          </ul>
          <Pager {...runs.data!} onChange={setRunsOffset} />
        </ResourceState>
      </Card>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-fg-muted">{label}</dt>
      <dd className="mt-0.5 break-words">{value}</dd>
    </div>
  );
}
function ResourceState({
  query,
  empty,
  children,
}: {
  query: {
    isPending: boolean;
    error: unknown;
    data?: { items: unknown[]; total: number; limit: number; offset: number };
  };
  empty: string;
  children: ReactNode;
}) {
  if (query.isPending) return <Skeleton lines={3} />;
  if (query.error) return <ErrorNotice error={query.error} />;
  if (query.data?.items.length === 0) return <EmptyState title={empty} />;
  return <>{children}</>;
}

export function SearchProfilesView() {
  const route = useRoute();
  const profileId = route.params.get("profile");
  const mode = route.params.get("mode");
  const list = useSearchProfiles();
  const profile = useSearchProfile(profileId);
  const capabilities = useSearchProfileCapabilities();
  const client = useQueryClient();
  const confirm = useConfirm();
  const [actionError, setActionError] = useState<unknown>(null);
  const editing = mode === "edit" || mode === "new";
  const selected = profile.data;
  const startNew = () => setParams({ profile: "new", mode: "new" });
  const open = (id: string) => setParams({ profile: id, mode: null });
  const afterSave = (saved: SearchProfile) => {
    void client.invalidateQueries({ queryKey: ["search-profiles"] });
    setParams({ profile: saved.id, mode: null });
  };
  const disable = async (target = selected) => {
    if (!target) return;
    const ok = await confirm({
      title: "Deactivate Search Profile?",
      message: "The profile will become inactive; its matches and run history remain preserved.",
      confirmLabel: "Deactivate",
      danger: true,
    });
    if (!ok) return;
    try {
      await api.disableSearchProfile(target.id);
      await client.invalidateQueries({ queryKey: ["search-profiles"] });
      await client.invalidateQueries({ queryKey: keys.searchProfile(target.id) });
    } catch (cause) {
      setActionError(cause);
    }
  };
  const header = (
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div>
        {profileId && !editing ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setParams({ profile: null, mode: null })}
          >
            <ArrowLeft size={14} aria-hidden="true" /> Search Profiles
          </Button>
        ) : null}
        <h1 className="text-lg font-semibold">Search Profiles</h1>
        <p className="text-sm text-fg-muted">
          Configure different search strategies without changing code.
        </p>
      </div>
      {!profileId ? (
        <Button variant="primary" onClick={startNew}>
          <Plus size={14} aria-hidden="true" /> New profile
        </Button>
      ) : null}
    </header>
  );
  if (editing)
    return (
      <section className="flex flex-col gap-4">
        {header}
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setParams({ profile: null, mode: null })}
          >
            <ArrowLeft size={14} /> Back
          </Button>
          <h2 className="text-base font-semibold">
            {mode === "new" ? "New Search Profile" : "Edit Search Profile"}
          </h2>
        </div>
        {mode !== "new" && profile.isPending ? (
          <Spinner label="Loading profile…" />
        ) : mode !== "new" && profile.error ? (
          <ErrorNotice error={profile.error} onRetry={() => profile.refetch()} />
        ) : capabilities.isPending ? (
          <Spinner label="Loading capabilities…" />
        ) : capabilities.error ? (
          <ErrorNotice error={capabilities.error} onRetry={() => capabilities.refetch()} />
        ) : (
          <ProfileForm
            key={mode === "new" ? "new" : (selected?.id ?? "loading")}
            profile={mode === "new" ? undefined : selected}
            capabilities={capabilities.data}
            onDone={afterSave}
            onCancel={() => setParams({ profile: null, mode: null })}
          />
        )}
      </section>
    );
  if (profileId)
    return (
      <section className="flex flex-col gap-4">
        {header}
        {profile.isPending ? (
          <Skeleton lines={6} />
        ) : profile.error ? (
          <ErrorNotice error={profile.error} onRetry={() => profile.refetch()} />
        ) : selected ? (
          <ProfileDetails profile={selected} />
        ) : null}
      </section>
    );
  return (
    <section className="flex flex-col gap-4">
      {header}
      {actionError ? <ErrorNotice error={actionError} /> : null}
      {list.isPending ? <Skeleton lines={5} /> : null}
      {list.error ? <ErrorNotice error={list.error} onRetry={() => list.refetch()} /> : null}
      {list.data?.items.length === 0 ? (
        <EmptyState
          title="Você ainda não criou uma estratégia de busca."
          action={
            <Button variant="primary" onClick={startNew}>
              <Plus size={14} /> Create first Search Profile
            </Button>
          }
        />
      ) : null}
      <div className="grid gap-3 lg:grid-cols-2">
        {list.data?.items.map((item) => (
          <Card key={item.id}>
            <button type="button" className="w-full text-left" onClick={() => open(item.id)}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h2 className="font-medium">{item.name}</h2>
                  <p className="mt-0.5 text-xs text-fg-muted">
                    {item.description || "No description."}
                  </p>
                </div>
                <Badge tone={item.enabled ? "positive" : "muted"}>
                  {item.enabled ? "Active" : "Inactive"}
                </Badge>
              </div>
              <dl className="mt-3 grid gap-2 text-xs text-fg-muted sm:grid-cols-2">
                <Detail
                  label="Roles"
                  value={item.target_roles.concat(item.role_aliases).join(", ") || "Not configured"}
                />
                <Detail
                  label="Location"
                  value={item.locations.concat(item.countries).join(", ") || "Not configured"}
                />
                <Detail label="Remote" value={humanize(item.remote_scope)} />
                <Detail label="Sources" value={item.sources.join(", ") || "Not configured"} />
                <Detail
                  label="Last run"
                  value={item.last_run_at ? formatDateTime(item.last_run_at) : "Never"}
                />
              </dl>
            </button>
            <div className="mt-3 flex flex-wrap gap-2 border-t border-edge pt-2">
              <Button size="sm" onClick={() => setParams({ profile: item.id, mode: "edit" })}>
                <Edit3 size={13} /> Edit
              </Button>
              {item.enabled ? (
                <Button size="sm" onClick={() => void disable(item)}>
                  <Pause size={13} /> Deactivate
                </Button>
              ) : null}
              <Button size="sm" onClick={() => open(item.id)}>
                View matches & runs
              </Button>
            </div>
          </Card>
        ))}
      </div>
    </section>
  );
}
