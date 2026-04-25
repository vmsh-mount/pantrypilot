# PantryPilot

Health-aware autonomous grocery agent for Swiggy Instamart. Runs a weekly **Sense → Plan → Optimize → Confirm → Place** loop that builds a nutritionally balanced basket for a household within budget, respecting every member's dietary constraints and allergies.

Built as a [Swiggy Builders Club](https://mcp.swiggy.com/builders/) submission (Developer track).

---

## Quick start

```bash
cd pantrypilot/
pip install -r requirements.txt
uvicorn pantrypilot.api:app --reload
# Open http://localhost:8000
```

The web UI auto-loads the Sharma household, shows the dietary filter (31 → 21 SKUs), then lets you run the optimizer and confirm or cancel the basket.

---

## How it's organised

```
pantrypilot/
├── context/
│   ├── design/             Per-feature design docs (api, optimizer, domain-model, …)
│   ├── learnings/          Dense context for resuming sessions
│   │   ├── project-context.md    ← start here when resuming
│   │   └── patterns.md           ← non-obvious patterns and gotchas
│   ├── Swiggy Builders Context - Grocery Automation.md
│   ├── Grocery Automation Responses.md   ← application form draft
│   └── PantryPilot Swiggy Proposal.docx
└── pantrypilot/            Python project
    ├── pantrypilot/        Package: models, optimizer, planner, api, static/
    ├── fixtures/           Demo household + mock Instamart catalogue
    ├── tests/              41 tests across 4 suites
    ├── requirements.txt
    └── README.md           Code-focused quick-start
```

## Quick links

| What | Where |
|---|---|
| **Resume a session** | `context/learnings/project-context.md` |
| **Run the web demo** | `cd pantrypilot/ && uvicorn pantrypilot.api:app --reload` |
| **Run all tests** | `cd pantrypilot/ && python3 tests/test_models.py && python3 tests/test_optimizer.py && python3 tests/test_planner.py && python3 tests/test_api.py` |
| API design | `context/design/api.md` |
| Optimizer design | `context/design/optimizer.md` |
| Domain model design | `context/design/domain-model.md` |
| Swiggy program rules | `context/Swiggy Builders Context - Grocery Automation.md` |
| Application form draft | `context/Grocery Automation Responses.md` |

## Build status

| Step | Description | Status |
|---|---|---|
| 1 | Domain model + fixtures + tests | ✅ Done (7 tests) |
| 2 | CP-SAT basket optimizer | ✅ Done (12 tests) |
| 3 | Planner loop with mock MCP client | ✅ Done (9 tests) |
| 4 | FastAPI surface + web UI | ✅ Done (13 tests) |
| 5 | Architecture diagram + submission | ⏳ Pending |
