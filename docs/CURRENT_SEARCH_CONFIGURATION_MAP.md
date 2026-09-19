# CURRENT_SEARCH_CONFIGURATION_MAP

Auditoria CAREER-01 — Fase 0. Produzida por inspeção read-only do repositório. Nenhum banco, serviço de produção, scheduler ou configuração operacional foi alterado.

## Escopo e evidência

- Repositório auditado: openings.
- Fonte operacional: YAML resolvido por OPENINGS_CONFIG ou, por padrão, $OPENINGS_DATA_DIR/config/settings.yaml.
- Desenvolvimento/Docker também usa settings.yaml na raiz, montado como /data/config/settings.yaml:ro.
- Não existe banco *.db no repositório; baseline de jobs/postings/events/runs não pôde ser calculado.
- Engineering MCP e Job Search MCP não estavam disponíveis; o inventário de MCP abaixo é do código local.

## Fluxo atual

YAML/environment -> parse_config -> Runtime.config -> collect_all(config)
-> JobSpy / ATS / RSS / JobCloud / Adzuna
-> normalização canônica + dedupe
-> score_jobs(config) -> thresholds
-> jobs.relevance_score + postings + runs
-> REST / dashboard / MCP

run_collection() é chamado pelo CLI ou scheduler. REST/MCP apenas criam o arquivo run-now; o scheduler o consome em até cerca de 30 segundos. Não existe run associado a perfil.

## CURRENT_SEARCH_CONFIGURATION_MAP

| CONFIG | SOURCE OF TRUTH ATUAL | CONSUMER | PODE MIGRAR PARA SEARCH PROFILE? | RISCO | COMPATIBILIDADE |
|---|---|---|---|---|---|
| profile.name/headline | profile no YAML; ProfileConfig | banner, /api/settings, MCP get_settings | Não; CandidateProfile | Misturar identidade e intenção | Preservar como dados do candidato |
| profile.target | YAML; ProfileConfig | resumo/configuração בלבד | Sim, com mapeamento explícito | Texto livre não alimenta collector | Não inferir roles |
| JobSpy enabled/sites | sources.jobspy.* | collect_all, _scrape, throttle | Sim para source; sites via capabilities | sites não são validados contra enum | Preservar legado; validar registry |
| JobSpy queries | sources.jobspy.queries; all_queries | run_jobspy; query x location x job_type | Sim: target_roles, aliases, include keywords | Separação role/keyword altera volume | Adapter deve reproduzir all_queries |
| JobSpy locations | sources.jobspy.locations | run_jobspy | Sim: locations/countries/remote scope | Remote hoje é texto de busca | Preservar comportamento textual no início |
| JobSpy job types | sources.jobspy.job_types | search_single_query; normalize_job_type | Sim: employment_types | Vocabulário externo | Reusar JOB_TYPES/aliases |
| JobSpy freshness | sources.jobspy.hours_old | argumento do JobSpy | Sim: freshness_days | Conversão dias/horas | Teste de equivalência |
| JobSpy remote | sources.jobspy.is_remote | argumento do JobSpy | Parcial: location_type/scope | Boolean não representa unknown | Nunca mapear false para rejected |
| JobSpy post-filter | post_filter.* | fuzzy_post_filter | Parcial; collection setting | Remove rows antes do score | Manter adapter legado inicialmente |
| JobSpy request controls | distance, country_indeed, results_wanted, offset, easy_apply, google_search_term, LinkedIn/proxy/cert | _scrape | Não são filtros de domínio | Exposição aumenta custo/risco | Permanecer administrativos |
| JobSpy throttling/retry/parallel | sources.jobspy.throttling/retry/parallel | throttle, tenacity, thread pool | Não em V1 de profile | Perfil pode causar carga excessiva | Manter global/server-side |
| Company ATS | sources.companies: name/ats/slug | collect_all -> FETCHERS[ats] | Sim se UI suportar companies | Cada adapter tem contrato | Capabilities deriva de FETCHERS |
| Company locations/titles | item de company | adapter e collect._keep | Parcial | Alguns adapters prefiltram internamente | Reusar location_kept; testar missing location |
| Company max age | item ou feed_max_age_days | fetch_company | Sim como freshness | precedência usa fallback por “or” | Documentar adapter |
| RSS feeds | sources.feeds[] | rss.fetch + _keep | Sim, source selection | URL é configuração operacional | Expor só feeds configurados |
| Adzuna | sources.adzuna.* | run_adzuna | Parcial | Requer país e secrets | Não criar capability fake |
| JobCloud | sources.jobcloud.* | run_jobcloud | Parcial | Inativo por default e limites próprios | Não mostrar sem suporte/configuração |
| HTTP global | user_agent, timeout_seconds, feed_max_age_days | todos/feeds/ATS | Não; administrativo | Misturar com estratégia | Manter global |
| Save/notify thresholds | scoring.save_threshold/notify_threshold | partition, retention, notifications | Não diretamente | Perfil pode exigir política própria | Preservar legado e definir transição |
| Scoring weights | scoring.weights | calculate_relevance_score/explain_score | Sim: scoring_weights | Pesos atuais específicos | Validar novo contrato; manter legado |
| Scoring keywords | scoring.keywords: terms/match_in/whole_word | matched_categories | Sim: roles/aliases/include/exclude/skills | Exclusion não é entidade hoje | Adapter preserva normalização/matching |
| Location score | categorias location_remote/location_target | scorer textual | Sim, com semântica explícita | Hoje é keyword, não eligibility | UNKNOWN não rejeita |
| Language/years/unrelated | keywords + pesos negativos | scorer textual | Parcial | Não inventar qualificação | Migrar como regra explicável |
| Runtime paths/secrets | OPENINGS_CONFIG, OPENINGS_DATA_DIR, env indirection | Runtime/CLI/Docker | Não | Dashboard não deve editar secrets | Sem alteração nesta wave |
| Scheduler | scheduler.* e run-now | openings scheduler | Futuramente enabled/schedule | Wave não pode ativar recorrência | Scheduler parado |
| Frontend filters | URL params + JobQuery | /api/jobs e Inbox | Não são strategy hoje | Só filtram pool salvo | Novo switch para matches |
| Stored score | jobs.relevance_score | DB, sort, Inbox, stats, notifications | Deve migrar para JobMatch | Mistura perfis e perde histórico | Fallback/legacy_score; não apagar |
| Runs | runs + RunSummary | pipeline, REST, MCP, Runs view | Deve evoluir para SearchRun | Sem profile_id/queries/duration persistidos | Migração aditiva; runs antigos sem profile |

## Adapters reais

O registry ATS contém: greenhouse, lever, ashby, smartrecruiters, workday, joincom, workable, rippling, bamboohr, oracle, personio, recruitee e breezy.

Também existem jobspy, rss, jobcloud, adzuna e manual. Greenhouse e Workday são reais; capabilities não deve incluir fonte não registrada.

collect_all() hoje recebe uma única configuração global e não aceita profile. Dedupe ocorre por posting key (URL canônica/external id) ou por identidade normalizada título+empresa+localização. jobs é canônico e postings representa aparições por fonte.

## Scoring atual

calculate_relevance_score soma uma vez o peso de cada categoria cujo termo aparece em title/description/company/location, respeitando match_in e whole_word. score_jobs cria relevance_score no DataFrame; upsert_jobs grava esse score no Job. prepare_runtime re-scoreia todos os Jobs ativos contra o YAML atual.

Não existe score(job, search_profile, candidate_profile), versionamento por perfil, breakdown persistido ou gap/reason de candidato. O scorer não lê CandidateProfile e não pode afirmar qualificação. Save threshold ocorre antes de persistir.

## REST, dashboard e MCP atuais

REST protegido por OPENINGS_API_TOKEN quando definido. Existem jobs, sources, runs, stats/facets/distribution, settings/reference, export e cleanup. Não existem endpoints CandidateProfile, SearchProfile, JobMatch ou SearchRun. POST /api/runs solicita o scheduler via run-now.

Frontend views: inbox, pipeline, companies, runs, system. Não há search-profiles. Inbox consulta /api/jobs com statuses=["new"] e jobs.relevance_score; não há profile selector.

MCP expõe tools read/write espelhando REST. Writes incluem add_job, status/labels/notes/attachments, delete/merge, cleanup e run_now. Não foi encontrada submission de application. Novas tools devem ser read-only para consulta e controladas para run, sem submission.

## Persistência, baseline e compatibilidade

schema.py usa executescript com CREATE TABLE IF NOT EXISTS e declara que não há migration. Tabelas relevantes: jobs, postings, events, runs, job_labels, notes, attachments e embeddings.

Não há schema_version, PRAGMA user_version, migration runner ou rollback. Não há data/db/openings.db no workspace, portanto before/after counts não são informáveis nesta fase. Capturar counts read-only no diretório real antes de migration.

O worktree já tinha alterações não relacionadas e não foram tocadas: Makefile e scripts/ não rastreados.

## Riscos prioritários

1. Migration deve ser aditiva, com rollback, sem reset/recreate.
2. Manter jobs.relevance_score até JobMatch cobrir consumidores; sem big-bang.
3. Refatorar coleta sem duplicar Job; cada perfil gera JobMatch após dedupe.
4. Preservar is_remote=None, localização ausente e eligibility unknown.
5. Capabilities devem derivar de registries reais, sem enums duplicados no frontend.
6. CandidateProfile só pode conter fatos evidenciados; unknown permanece unknown.
7. Scheduler permanece STOPPED; esta auditoria não o iniciou.

## Plano/diff proposto antes da implementação

- CAREER-01A: entidades/validação + migration aditiva + adapter de configuração legada.
- CAREER-01B: CRUD REST/service, capabilities, matches/runs, auth e eventos.
- CAREER-01C: view Search Profiles com progressive disclosure e estados obrigatórios.
- CAREER-01D/E: collector parametrizado por profile, dedupe global, scorer determinístico e JobMatch.
- CAREER-01F/G: Inbox por profile, compatibilidade do pipeline, baseline/regressão, TDD e E2E mockado.

Nenhuma destas subwaves foi implementada nesta Fase 0.
