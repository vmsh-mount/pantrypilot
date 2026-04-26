# PantryPilot — Production Architecture

```mermaid
flowchart TD
    CLIENT["🧑‍💻 Swiggy App / Browser"]

    GW["API Gateway\nAuth · Rate-limit · Routing"]

    subgraph SVC["PantryPilot API — FastAPI · stateless · horizontally scaled"]
        direction LR
        HH["POST /household\nSave household & members"]
        CAT["GET /catalogue\nDietary filter + compatible SKUs"]
        CYCLE["POST /cycle\nEnqueue optimisation job"]
        CONFIRM["POST /cycle/{id}/confirm\nConfirm or cancel basket"]
    end

    subgraph WORKER["Optimisation Worker — async"]
        Q["Job Queue"]
        W["CP-SAT Solver\nOR-Tools"]
        Q --> W
    end

    subgraph DATA["Data Layer"]
        PG[("PostgreSQL\nhouseholds · members\npantry state · order history")]
        REDIS[("Redis\nsession store — 4h TTL\ncatalogue cache — 5min TTL\njob queue")]
    end

    subgraph PLATFORM["Swiggy Platform"]
        AUTH["Auth SSO\nJWT / OAuth2"]
        MCP["Instamart MCP\ncatalogue · pricing · stock\n(nutrition data implied)"]
        ORDERAPI["Order API\nbasket submission"]
        WHOOK["Delivery Webhook\npantry update on delivery"]
    end

    subgraph INFRA["Infrastructure"]
        K8S["Kubernetes\ncontainer orchestration"]
        OBS["Observability\nlogs · metrics · traces"]
        CICD["CI/CD — GitHub Actions"]
    end

    CLIENT -->|HTTPS| GW
    GW -->|validate JWT| AUTH
    GW --> SVC

    HH -->|read / write| PG
    CAT -->|check cache| REDIS
    REDIS -->|cache miss| MCP
    CYCLE -->|enqueue job| REDIS
    REDIS -->|dequeue| W
    W -->|write result| REDIS
    W -->|update pantry| PG
    CONFIRM -->|read session| REDIS
    CONFIRM -->|place order| ORDERAPI
    ORDERAPI -->|on delivery| WHOOK
    WHOOK -->|update pantry state| PG

    SVC -.->|emit| OBS
    WORKER -.->|emit| OBS
    K8S -.->|orchestrates| SVC
    K8S -.->|orchestrates| WORKER
```

## Demo → Production delta

| Concern | Demo | Production |
|---------|------|------------|
| Household store | In-memory dict | PostgreSQL |
| Session store | In-memory dict | Redis (4h TTL) |
| Catalogue | Fixture (67 mock SKUs) | Instamart MCP (live catalogue) |
| Optimisation | Synchronous in-process | Async job queue → CP-SAT worker |
| Order placement | Mock `place_confirmed()` | Swiggy Order API |
| Pantry update | Manual / fixture | Delivery webhook → PostgreSQL |
| Auth | None | Swiggy SSO (JWT / OAuth2) |
| Scaling | Single process | Stateless API pods + worker pool (K8s) |
| Nutrition data | Hardcoded in fixtures | Served by Instamart MCP |

## Key production properties

**Stateless API pods.** All shared state lives in PostgreSQL or Redis. Any pod can handle any request — scale horizontally without coordination.

**Async optimisation.** `POST /cycle` enqueues a job and returns immediately with a job ID. The client polls or receives a push notification when the result is ready. Prevents slow CP-SAT solves (large households, wide catalogues) from blocking the API.

**Catalogue cache.** Instamart pricing and stock change frequently; nutrition data does not. Redis caches the filtered catalogue per household for 5 minutes — reduces MCP round-trips on repeat optimisations.

**Pantry closed-loop.** The delivery webhook fires when Swiggy marks an order delivered, decrementing pantry quantities automatically. The next cycle starts with fresh pantry state.

**Strictest-wins is safe to scale.** Dietary/allergy filtering is stateless and deterministic — it runs in the API worker with no external calls, so it adds no latency to the catalogue fetch path.
