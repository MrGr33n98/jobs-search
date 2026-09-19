import { useMemo } from "react";

import type { ReviewStatus } from "../../api/types";
import { navigate, setParams, useRoute } from "../../app/router";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { EmptyState, ErrorNotice, Skeleton } from "../../components/EmptyState";
import { Input, Select } from "../../components/Field";
import { useProfileActions, useSearchProfileMatches, useSearchProfiles } from "../shared/queries";

const REVIEW_OPTIONS: { value: ReviewStatus; label: string }[] = [
  { value: "new", label: "New" },
  { value: "interested", label: "Interested" },
  { value: "saved", label: "Saved" },
  { value: "dismissed", label: "Dismissed" },
];

export function ProfileInbox({ profileId }: { profileId: string }) {
  const route = useRoute();
  const profiles = useSearchProfiles();
  const minScoreValue = route.params.get("min_score") ?? "";
  const reviewStatus = route.params.get("review_status") ?? "";
  const matches = useSearchProfileMatches(profileId, {
    limit: 50,
    offset: Number(route.params.get("match_offset") ?? 0),
    min_score: minScoreValue ? Number(minScoreValue) : undefined,
    review_status: reviewStatus || undefined,
  });
  const actions = useProfileActions(profileId);
  const selected = profiles.data?.items.find((profile) => profile.id === profileId);
  const items = useMemo(() => matches.data?.items ?? [], [matches.data]);

  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-2 rounded-lg border border-edge bg-surface p-3">
        <label className="flex min-w-56 flex-1 flex-col gap-1 text-xs font-medium text-fg-muted">
          Search Profile
          <Select
            aria-label="Search Profile"
            value={profileId}
            onChange={(event) => setParams({ profile: event.target.value, match_offset: null })}
          >
            {profiles.data?.items.map((profile) => (
              <option key={profile.id} value={profile.id}>
                {profile.name}
              </option>
            ))}
          </Select>
        </label>
        <label className="flex w-28 flex-col gap-1 text-xs font-medium text-fg-muted">
          Score ≥
          <Input
            aria-label="Minimum match score"
            type="number"
            min={0}
            max={100}
            value={minScoreValue}
            onChange={(event) => setParams({ min_score: event.target.value, match_offset: null })}
          />
        </label>
        <label className="flex w-36 flex-col gap-1 text-xs font-medium text-fg-muted">
          Review
          <Select
            aria-label="Review status"
            value={reviewStatus}
            onChange={(event) =>
              setParams({ review_status: event.target.value, match_offset: null })
            }
          >
            <option value="">All</option>
            {REVIEW_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </label>
        <span className="pb-2 text-xs text-fg-muted">
          {selected?.name ?? "Search Profile"} · {matches.data?.total ?? 0} matches
        </span>
      </div>
      {matches.error ? (
        <ErrorNotice error={matches.error} onRetry={() => matches.refetch()} />
      ) : null}
      {matches.isPending ? <Skeleton lines={6} /> : null}
      {!matches.isPending && !matches.error && items.length === 0 ? (
        <EmptyState title="No compatible jobs found">
          Nenhuma vaga compatível foi encontrada para este perfil.
        </EmptyState>
      ) : null}
      <div className="divide-y divide-edge rounded-lg border border-edge bg-surface">
        {items.map((item) => (
          <article
            key={item.match.id}
            className="flex flex-wrap items-start justify-between gap-3 p-3"
          >
            <button
              type="button"
              className="min-w-0 flex-1 text-left"
              onClick={() => navigate({ jobId: item.job.job_id })}
            >
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="font-medium text-fg">{item.job.title}</h2>
                <Badge tone="accent">{item.match.score} match score</Badge>
                <Badge>{item.match.eligibility}</Badge>
                <Badge>{item.match.review_status}</Badge>
              </div>
              <p className="mt-1 text-xs text-fg-muted">
                {item.job.company} · {item.job.location || "Location unknown"} · {item.job.source}
              </p>
              {item.match.match_reasons.length ? (
                <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-fg-muted">
                  {item.match.match_reasons.slice(0, 3).map((reason) => (
                    <li key={reason}>✓ {reason}</li>
                  ))}
                </ul>
              ) : null}
            </button>
            <div className="flex flex-wrap items-center gap-1">
              {REVIEW_OPTIONS.filter((option) => option.value !== item.match.review_status)
                .slice(0, 2)
                .map((option) => (
                  <Button
                    key={option.value}
                    size="sm"
                    variant="ghost"
                    disabled={actions.review.isPending}
                    onClick={() =>
                      actions.review.mutate({ jobId: item.job.job_id, status: option.value })
                    }
                  >
                    {option.label}
                  </Button>
                ))}
              <Button
                size="sm"
                disabled={actions.addToPipeline.isPending}
                onClick={() => actions.addToPipeline.mutate(item.job.job_id)}
              >
                Add to Pipeline
              </Button>
            </div>
          </article>
        ))}
      </div>
      {matches.data && matches.data.total > matches.data.offset + matches.data.items.length ? (
        <Button
          className="self-center"
          variant="ghost"
          onClick={() =>
            setParams({ match_offset: String(matches.data!.offset + matches.data!.items.length) })
          }
        >
          Load more
        </Button>
      ) : null}
    </section>
  );
}
