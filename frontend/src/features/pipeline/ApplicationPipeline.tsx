import { useMemo } from "react";

import type { ApplicationStage } from "../../api/types";
import { navigate } from "../../app/router";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { EmptyState, ErrorNotice, Skeleton } from "../../components/EmptyState";
import { useApplications } from "../shared/queries";

const STAGES: ApplicationStage[] = [
  "interested",
  "preparing",
  "ready_to_apply",
  "applied",
  "interviewing",
  "offer",
  "rejected",
  "withdrawn",
];

const label = (stage: string) => stage.replaceAll("_", " ");

export function ApplicationPipeline() {
  const query = useApplications({ limit: 100 });
  const columns = useMemo(
    () =>
      STAGES.map((stage) => ({
        stage,
        items: query.data?.items.filter((item) => item.application.stage === stage) ?? [],
      })),
    [query.data],
  );
  if (query.error) return <ErrorNotice error={query.error} onRetry={() => query.refetch()} />;
  if (query.isPending) return <Skeleton lines={6} />;
  if (!query.data?.total) {
    return (
      <EmptyState title="Nothing in the application pipeline">
        Add a reviewed match to the Pipeline when you explicitly want to prepare an application.
      </EmptyState>
    );
  }
  return (
    <div className="flex gap-3 overflow-x-auto pb-3">
      {columns.map((column) => (
        <section
          key={column.stage}
          className="min-w-64 rounded-lg border border-edge bg-surface-2/50"
        >
          <header className="flex items-center justify-between px-3 py-2">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-fg-muted">
              {label(column.stage)}
            </h2>
            <Badge>{column.items.length}</Badge>
          </header>
          <div className="flex flex-col gap-2 p-2">
            {column.items.map((item) => (
              <article
                key={item.application.id}
                className="rounded-md border border-edge bg-surface p-3"
              >
                <button
                  type="button"
                  className="text-left font-medium hover:underline"
                  onClick={() => navigate({ jobId: item.job.job_id })}
                >
                  {item.job.title}
                </button>
                <p className="mt-1 text-xs text-fg-muted">
                  {item.job.company} · {item.job.location || "Location unknown"}
                </p>
                {item.source_search_profile_name ? (
                  <p className="mt-2 text-[11px] text-fg-faint">
                    From {item.source_search_profile_name}
                  </p>
                ) : null}
              </article>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
