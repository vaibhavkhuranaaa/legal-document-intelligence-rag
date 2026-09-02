# ADR-0020: Stay on App Service and drop to the Free plan

## Decision

Eliminate the fixed application host cost by changing the existing App Service
plan from B1 to F1, rather than migrating to Azure Container Apps. Keep the
application, hostname, runtime, identity, settings and deployment workflow
exactly as they are.

The decision is recorded now. The plan change itself is deferred and needs its
own approval, because it briefly interrupts a live service.

## Why

The migration this project had planned was framed while it was paying 73.73 USD
per month for a Basic Search service. That charge is gone. What remains is a B1
Linux plan at 0.017 USD per hour, or 12.41 USD per month, and a migration that
made sense against 86 USD does not automatically make sense against 12.

Two facts decided it.

Container Apps cannot serve `app-legal-rag-prod-278f1d.azurewebsites.net`. It
serves `<name>.<region>.azurecontainerapps.io`. That hostname is pinned by the
public portfolio, cited across the delivery record, and requested by every
recorded evidence check. Keeping a stable URL through a Container Apps cutover
requires a custom domain and a certificate the project does not have. The
milestone had asked for a Container Apps migration that preserved the public URL
contract, which is not a thing that can be built.

The objection to the Free plan was its 60 CPU minute daily quota, which stops
the app until UTC midnight when exhausted. That objection was measurable, and
measuring it settled the question. `CpuTime` is the same meter the Free tier
enforces against, so eight days of production consumption were read directly:

| Day | CpuTime seconds | Share of the 3,600 second quota |
| --- | --- | --- |
| 2026-08-26 | 45.1 | 1.25% |
| 2026-08-27 | 65.5 | 1.82% |
| 2026-08-28 | 40.8 | 1.13% |
| 2026-08-29 | 31.7 | 0.88% |
| 2026-08-30 | 32.8 | 0.91% |
| 2026-08-31 | 32.6 | 0.90% |
| 2026-09-01 | 30.9 | 0.86% |
| 2026-09-02 | 18.5 | 0.51% |

The worst day used 1.82 percent of the allowance. A controlled burst of 42
requests consumed 0.17 CPU seconds in total, which is roughly 0.004 seconds per
request. At that marginal rate the daily quota would absorb hundreds of
thousands of requests.

Daily CPU does not track traffic at all: the heaviest day served six requests
and the lightest served forty-five. At one minute resolution the application
draws a flat 0.02 CPU seconds per minute whether or not it is serving anything,
which is about 29 seconds a day and accounts for nearly the whole figure. The
quota is consumed by existing, not by working.

## Alternatives rejected

- Azure Container Apps on the Consumption plan was rejected on the URL contract.
  Its running cost would genuinely be zero inside the monthly free grant, but it
  requires an image, a registry, an environment, a new deployment and
  verification workflow, and either a new public URL or a domain purchase. It
  also carries two cost traps: a Basic container registry adds 5.07 USD per
  month, and a Dedicated workload profile or private endpoint adds 0.10 USD per
  hour, which is six times the charge being removed.
- Staying on B1 was rejected because 12.41 USD per month buys dedicated CPU that
  the measurements show this workload does not use.
- The Shared plan was rejected because it bills 0.013 USD per hour, so it costs
  nearly as much as B1 while accepting quota limits similar to Free.

## Not done

No plan SKU has changed. No Container Apps resource, image, registry or
environment exists. The application, its hostname, its runtime, its settings and
its deployment workflow are untouched by this record.

## Changed

Three corrections were applied to production alongside this decision, each
verified against the live system afterwards.

The application identity `id-legal-rag-prod` no longer holds
`Storage Blob Data Contributor`. The web application has no storage settings and
no storage code path, so it never used that write access. It now holds only
`Cognitive Services OpenAI User` and `Search Index Data Reader`.

The live startup command now reads
`gunicorn --bind 0.0.0.0:8000 --timeout 120 legal_rag.ui.flask_app:app`,
matching `startup.txt`. It had omitted the timeout flag, so production had been
running on the gunicorn default of 30 seconds while the record claimed 120. No
request had yet failed on it, but a slow generation would have been cut off and
presented as an error rather than a wait.

A metric alert now fires when 24 hour `CpuTime` passes 2,880 seconds, which is
80 percent of the Free tier allowance. Before this there was no telemetry and no
alerting of any kind, so quota exhaustion would first have been visible to a
visitor receiving a 403.

## What would change this decision

Traffic growing until the CPU quota is genuinely at risk, which the alert now
reports before it happens. A need for a custom domain, which the Free plan
cannot serve and which would reopen the Container Apps comparison on equal
terms. Or a requirement for an availability guarantee, which no Free plan makes.
