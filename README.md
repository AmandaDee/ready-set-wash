# Ready, Set, Wash

The right time for a lighter load. A personal portfolio project that finds a cheaper window to run a washing machine
using Octopus Energy electricity prices, Python and GraphQL.

I wanted a small, useful application with an interesting problem behind it: a cycle can cross multiple tariff intervals,
prices can be negative, and UK clock changes make naïve time arithmetic unreliable. Ready, Set, Wash turns that into a
simple interface: choose a duration and deadline; see a recommended start and comparison with starting now.

![Ready, Set, Wash demo: choosing a cycle and finding the cheapest wash window](docs/demo.gif)

## Run it locally

You need **Python 3.12+**. Node 24.15+ is needed only to run frontend tests; the app itself has no Node build step.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pip install --no-deps -e .
cp .env.example .env
uvicorn ready_set_wash.app:create_app --factory --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. Demo mode works without credentials. For development, add `--reload` to the server
command.

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1` and copy with `Copy-Item .env.example .env`. If
activation is restricted, use `.venv\Scripts\python.exe -m pip` and `.venv\Scripts\python.exe -m uvicorn` directly. Run
commands from this project's root so `.env` is loaded.

## Use real Octopus prices

1. Find your exact electricity **product code** and **tariff code**, including the regional suffix, using
   the [Octopus products API](https://api.octopus.energy/v1/products/) or your account's tariff information.
2. Set these values in your local `.env`:

```dotenv
READY_SET_WASH_MODE=live
READY_SET_WASH_PRODUCT_CODE=YOUR-PRODUCT-CODE
READY_SET_WASH_TARIFF_CODE=YOUR-TARIFF-CODE
READY_SET_WASH_OCTOPUS_API_KEY=
```

3. Restart the server. The badge changes to “Live Octopus prices”.

Public unit prices do **not** require an API key. `READY_SET_WASH_OCTOPUS_API_KEY` is a server-only, redacted
configuration slot for future authenticated account integrations; the current application does not send or use it. Do
not put keys in frontend code. `.env` and `.env.*` are ignored by Git; only the empty `.env.example` template belongs in
the repository. Before your first commit, check `git check-ignore .env` and review `git diff --cached`.

The frontend consumes **this application's Strawberry GraphQL API**, while the Python provider retrieves prices from
Octopus's documented public REST price endpoint. This project does not consume Octopus's authenticated Kraken GraphQL
API. That separation keeps the demo accessible and avoids asking visitors to connect an account. Native Kraken account
queries can be added behind the provider boundary later, following Octopus's authentication guidance.

Live integration is tested with mocked HTTP responses. You must verify your chosen tariff against actual Octopus
responses locally; no real account credentials are included or used in this repository.

## How the estimate works

`domain.py` is pure Python, independent of the web framework. It integrates the 0.8 kWh reference wash evenly over the
cycle's duration and each overlapping price interval. Candidate starts include now, the latest allowed start and
boundaries at either end of the cycle. That captures extrema of the piecewise-linear cost function without sampling
every minute.

Prices are represented with `Decimal`; timestamps are converted to UTC before duration arithmetic. Gaps invalidate a
candidate; overlapping rates are rejected. Equal costs choose the earliest start. The frontend displays times in
`Europe/London`, even if your computer uses another timezone. Nonexistent spring-forward times are rejected; repeated
autumn times resolve to the later occurrence.

Real machines do not consume power evenly. Costs are estimates, not bill calculations. Standing charges are excluded
because moving a wash does not change the daily standing charge. Agile prices may not yet be published for your full
deadline; the planner uses only complete available windows and reports an error if none fit. It never invents live
prices or falls back silently to demo mode.

## Project structure

```text
src/ready_set_wash/
  config.py        Typed environment settings and secret redaction
  domain.py        Immutable models and pure cost optimisation
  providers.py     Demo/live prices, bounded timeout and short-lived cache
  schema.py        Typed GraphQL contract and query limits
  app.py           Application factory and HTTP resource lifecycle
  security.py      Streaming request limits and security headers
  static/          Modular browser UI, chart, history and time helpers
tests/             Domain, integration, security and browser-helper tests
.github/workflows/ Automated quality checks
```

The frontend uses native ES modules and CSS. This is deliberately small: no framework build pipeline, CDN scripts,
external fonts or JavaScript runtime dependencies. Backend HTTP resources are created and closed through the application
lifespan; the upstream cache is isolated per app instance.

## Test

```bash
pytest
ruff check .
ruff format --check .
mypy src
npm ci
npm test
```

Python tests collect **line and branch coverage** and fail below **90%**. Open `htmlcov/index.html` after running them
to inspect coverage. Browser-helper tests cover GraphQL failures, UK DST handling, calendar output and resilient
storage. Frontend tests also enforce at least 90% line, branch and function coverage across all application JavaScript
modules, including DOM integration tests. HTML and CSS are not executable-code coverage targets.

The GitHub Actions workflow runs linting, formatting, strict type checking and both test suites. Dependency versions are
pinned for reproducible installations. Dependabot proposes updates; review changes and rerun checks before merging.

## Security and operating scope

Designed for a single person running on their own computer:

- Default run command binds to loopback; trusted host validation rejects other hostnames.
- Same-origin checks and JSON-only POSTs reduce browser-based cross-origin attacks.
- A small request-body limit and GraphQL token, alias and depth limits constrain work.
- CSP, no-sniff, no-referrer and no-store response headers; no `innerHTML` rendering of API data.
- Upstream is fixed to `https://api.octopus.energy`; tariff identifiers cannot alter its host or path structure.
  Redirects are disabled and failures return a safe message.
- Credentials never enter GraphQL responses, browser storage or logs.
- No external analytics and no account details persisted.

There is no multi-user authentication, shared database or distributed rate limiter. Before exposing it on the internet,
add authentication, HTTPS, reverse-proxy request limits, a deployment-specific host allowlist and operational
monitoring. This is a production-style **local personal application**, not a claim of an audited public service.

## API example

Send JSON to `POST /graphql` with a timezone-aware deadline in the next 48 hours:

```graphql
query Wash($deadline: DateTime!) {
  dashboard(deadline: $deadline, durationMinutes: 90) {
    mode
    plan { start end costPence nowCostPence savingsPence }
    prices { start end pencePerKwh }
  }
}
```

GraphQL errors appear in the `errors` array, including when HTTP status is 200. The frontend checks both. The browser
GraphQL IDE is disabled; use your preferred API client.

## References

- [Octopus REST price endpoint](https://docs.octopus.energy/rest/guides/endpoints/)
- [Octopus GraphQL API guidance](https://developer.octopus.energy/guides/graphql/api-basics/)
- [Strawberry GraphQL](https://strawberry.rocks/docs)
- [FastAPI](https://fastapi.tiangolo.com/)

Independent project; not affiliated with or endorsed by Octopus Energy.
