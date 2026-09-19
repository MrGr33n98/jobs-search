"""Deterministic translation from a SearchProfile to collection inputs."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from openings.career import SearchProfile
from openings.config import Config

if TYPE_CHECKING:
    from openings.config import CompanySourceConfig, FeedSourceConfig


class CollectionPlanError(ValueError):
    """The selected strategy cannot be translated to supported adapters."""


@dataclass(frozen=True)
class CollectionPlan:
    profile_id: str
    sources: tuple[str, ...]
    queries: tuple[str, ...]
    locations: tuple[str, ...]
    employment_types: tuple[str, ...]
    freshness_days: int | None
    jobspy_country: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProfileCollectionConfig:
    """Effective strategy inputs; operational settings stay in ``Config``."""

    config: Config
    plan: CollectionPlan


def _jobspy_country(countries: tuple[str, ...]) -> tuple[str, str | None]:
    if not countries:
        return "worldwide", None
    candidate = countries[0].strip().lower()
    try:
        from jobspy.model import Country

        Country.from_string(candidate)
    except ImportError:
        # Tests and minimal installations may intentionally omit JobSpy. Keep
        # the boundary deterministic with the aliases from its public enum.
        known = {
            "argentina",
            "australia",
            "brazil",
            "canada",
            "chile",
            "colombia",
            "germany",
            "india",
            "mexico",
            "portugal",
            "spain",
            "uk",
            "united kingdom",
            "usa",
            "united states",
            "worldwide",
        }
        if candidate not in known:
            return "worldwide", f"unsupported JobSpy country {countries[0]!r}; using worldwide"
    except ValueError:
        return "worldwide", f"unsupported JobSpy country {countries[0]!r}; using worldwide"
    return candidate, None


def build_collection_plan(
    profile: SearchProfile, capabilities: dict[str, object], global_config: Config
) -> CollectionPlan:
    """Build the same plan for the same inputs, without mutating global config."""
    source_rows = capabilities.get("sources", [])
    available: dict[str, bool] = {}
    enabled: dict[str, bool] = {}
    for row in source_rows if isinstance(source_rows, list) else []:
        if isinstance(row, dict) and isinstance(row.get("id"), str):
            available[row["id"]] = bool(row.get("available"))
            enabled[row["id"]] = bool(row.get("enabled"))
    selected = tuple(dict.fromkeys(profile.sources))
    if not selected:
        raise CollectionPlanError("search profile must select at least one source")
    invalid = [source for source in selected if not available.get(source, False)]
    if invalid:
        raise CollectionPlanError(f"unsupported search profile source: {invalid[0]}")
    unavailable = [source for source in selected if not enabled.get(source, False)]
    if unavailable:
        raise CollectionPlanError(
            f"search profile source is unavailable in the current configuration: {unavailable[0]}"
        )

    queries = tuple(
        dict.fromkeys(
            value.strip()
            for value in (*profile.target_roles, *profile.role_aliases, *profile.include_keywords)
            if value.strip()
        )
    )
    if "jobspy" in selected and not queries:
        raise CollectionPlanError("JobSpy requires at least one target role or include keyword")

    locations = tuple(dict.fromkeys((*profile.locations, *profile.countries)))
    if not locations and "jobspy" in selected:
        locations = tuple(global_config.sources.jobspy.locations)
    if not locations and "jobspy" in selected:
        locations = ("Remote",)
    country, warning = _jobspy_country(profile.countries)
    warnings = (warning,) if warning else ()
    return CollectionPlan(
        profile_id=profile.id,
        sources=selected,
        queries=queries,
        locations=locations,
        employment_types=tuple(profile.employment_types),
        freshness_days=profile.freshness_days,
        jobspy_country=country,
        warnings=warnings,
    )


def _company_sources(
    config: Config, sources: tuple[str, ...], profile: SearchProfile, plan: CollectionPlan
) -> list[CompanySourceConfig]:
    titles = list(
        dict.fromkeys((*profile.target_roles, *profile.role_aliases, *profile.include_keywords))
    )
    locations = list(plan.locations)
    return [
        replace(
            company,
            titles=titles or list(company.titles),
            locations=locations or list(company.locations),
            max_age_days=plan.freshness_days or company.max_age_days,
        )
        for company in config.sources.companies
        if company.ats in sources
    ]


def _feed_sources(config: Config, profile: SearchProfile) -> list[FeedSourceConfig]:
    locations = list(profile.locations or profile.countries)
    titles = list(
        dict.fromkeys((*profile.target_roles, *profile.role_aliases, *profile.include_keywords))
    )
    if not locations:
        return list(config.sources.feeds)
    return [
        replace(feed, locations=locations, titles=titles or list(feed.titles))
        for feed in config.sources.feeds
    ]


def effective_collection_config(
    profile: SearchProfile, plan: CollectionPlan, global_config: Config
) -> ProfileCollectionConfig:
    """Compose strategy with a deep copy; the runtime/YAML config is untouched."""
    import copy

    config = copy.deepcopy(global_config)
    # Profile collection must feed the canonical pool even when the legacy
    # YAML threshold would have filtered a row before CAREER-01E can score it.
    # This changes only the private copy, never the runtime config or YAML.
    config.scoring.save_threshold = 0
    sources = set(plan.sources)
    jobspy = config.sources.jobspy
    jobspy.enabled = "jobspy" in sources
    jobspy.queries = {"search_profile": list(plan.queries)}
    jobspy.locations = list(plan.locations)
    jobspy.job_types = list(plan.employment_types) or list(jobspy.job_types)
    jobspy.country_indeed = plan.jobspy_country
    if plan.freshness_days is not None:
        jobspy.hours_old = plan.freshness_days * 24
    config.sources.companies = _company_sources(config, plan.sources, profile, plan)
    config.sources.feeds = _feed_sources(config, profile) if "rss" in sources else []
    config.sources.jobcloud.enabled = "jobcloud" in sources
    config.sources.adzuna.enabled = "adzuna" in sources
    if "jobcloud" in sources:
        config.sources.jobcloud.queries = list(plan.queries)
        config.sources.jobcloud.locations = list(plan.locations)
    if "adzuna" in sources:
        config.sources.adzuna.queries = list(plan.queries)
        config.sources.adzuna.locations = list(plan.locations)
    return ProfileCollectionConfig(config=config, plan=plan)


def excluded_keywords_filter(frame, keywords: tuple[str, ...]):
    """Apply exclusions after collection; missing fields remain UNKNOWN, not rejected."""
    if frame.empty or not keywords:
        return frame
    lowered = tuple(keyword.casefold() for keyword in keywords)

    def keep(row) -> bool:
        text = " ".join(
            str(row.get(column) or "") for column in ("title", "company", "location", "description")
        )
        return not any(keyword in text.casefold() for keyword in lowered)

    return frame.loc[frame.apply(keep, axis=1)].copy()
