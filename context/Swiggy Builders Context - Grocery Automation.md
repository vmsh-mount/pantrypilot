# Swiggy Builders Club — Context Reference

> Source: https://mcp.swiggy.com/builders/ and https://mcp.swiggy.com/builders/access/
> Captured: April 2026
> Purpose: Reference doc for PantryPilot project — keeps Swiggy's program rules, evaluation criteria, and constraints front-of-mind in every chat.

---

## What the Program Is

Swiggy's MCP partnership platform for developers, startups, and enterprises to build AI agents, apps, and integrations on top of Swiggy's Food, Instamart, and Dineout APIs.

- 3 MCP servers exposed: Food, Instamart, Dineout
- 18+ API tools available
- Two tracks: Developer (indie/small team) and Enterprise (companies with custom SLAs)
- Contact: builders@swiggy.in

## Stated Program Goals

- "Build real products" with live APIs and real users (not mock endpoints)
- "AI-Native from Day One" — designed for agents, copilots, automations
- "Experiment Freely" — generous rate limits, direct engineering support
- "Get Noticed by Swiggy" — standout projects get featured; they hire from the program

## How It Works (5 Steps)

1. **Apply** — ~5 minute form covering who you are and what you're building
2. **Quick Review** — Swiggy reviews use case, security, fit
3. **Get Access** — API keys, credentials, documentation
4. **Build & Ship** — iterate fast
5. **Show Us What You Built** — demo submission; great projects get featured

## What Swiggy Checks During Review

1. **Security Check** — security setup and infrastructure
2. **Compliance Review** — data handling and privacy practices
3. **Use Case Fit** — alignment with platform and users
4. **Gradual Rollout** — validate together, ramp access gradually
5. **Ongoing Partnership** — usage monitoring, support, direct line to team

## What Swiggy Wants in Applications

**Required:**
- Identity (company or individual developer profile)
- Use case description
- Integration architecture overview
- Redirect URI(s) for auth flows
- Static IP ranges or gateway IP(s)
- Security contact for the team
- Data handling and privacy declaration
- Environment and infrastructure setup details
- Acknowledgement of Swiggy MCP terms

**Optional but helpful:**
- Security audit summary
- SOC2 / ISO certification
- Expected traffic and scaling plan

## What Swiggy Provides

- Live API access (production data)
- Generous default rate limits, expandable on request
- "Powered by Swiggy" co-branding (use of brand assets)
- Direct engineer support, integration help, Slack channel
- Growth partnership: co-marketing, strategic support for builders who ship

---

## Ground Rules — Critical Reference

### ✅ Encouraged

- Apps, agents, or tools that improve ordering, discovery, or dining
- AI-powered assistants and copilots automating commerce workflows
- Creative side projects, hackathon builds, experimental prototypes
- Integrations following security and branding guidelines
- Sharing demos and walkthroughs
- Commercial partnerships with mutual upside

### ❌ Not Allowed

- Reselling or sharing MCP access with unapproved third parties
- Building aggregation layers that hide Swiggy's brand or confuse users
- Misrepresenting prices, availability, or delivery times
- Scraping or extracting data beyond what the APIs provide
- Using the APIs for competitive intelligence or benchmarking
- Bypassing rate limits, logging, or any platform safeguards

### 🚫 Prohibited Conduct (Zero Tolerance)

1. Manipulating order flows, incentives, or ranking systems
2. Dark patterns, deceptive UX, or misattributing where data comes from
3. Generating fake traffic or abusing rate limits
4. Harvesting data beyond agreed scope
5. Reverse engineering MCP internals
6. Circumventing whitelisting or access controls
7. Violating user privacy or security regulations

### Four Operating Principles

1. **Stay in Scope** — use APIs for what they're built for; new capabilities require conversation
2. **Respect the Brand** — follow Swiggy's attribution guidelines; users should know when they're interacting with Swiggy services
3. **User Data is Sacred** — transaction data from MCP stays governed by Swiggy's platform terms
4. **We Keep Watch** — usage is monitored for quality and safety

---

## Implications for PantryPilot

These rules directly shape product decisions — refer back when designing any feature:

| Swiggy rule | PantryPilot design implication |
|---|---|
| No misrepresenting prices/availability | All prices/stock shown to users must be live MCP responses, never inferred or stale |
| No aggregation hiding the brand | "Powered by Swiggy Instamart" lockup on every basket, confirmation, and receipt |
| No dark patterns | Auto-confirm has a 4-hour window with one-tap cancel; pause-forever from any message |
| No competitive intelligence | Never compare Instamart prices to other platforms in user UI or internal analytics |
| No order-flow manipulation | Optimizer is transparent — user can inspect why each item was added |
| Stay in scope | MCP used only for authenticated user's own grocery loop; no bulk/speculative queries |
| Data sacred | MCP data never resold, never shared with third parties, never used to train external models |

## Application Tracks

- **Developer track** (indie hackers, solo devs, small teams, startups) → faster turnaround, applies for PantryPilot v1
- **Enterprise track** (companies needing dedicated support, SLAs, custom terms) → ~4+ week legal turnaround

PantryPilot applies under **Developer track**.

## Legal Framework Mentioned

- MCP integration agreement
- Data protection & privacy terms
- Liability and misuse provisions
- Termination and revocation rights
- Custom terms negotiable for enterprise partners (4+ week turnaround)

---

## Quick Tone Notes

Swiggy's program voice is informal-but-disciplined ("no hoops, no gatekeeping," "no surprises," "play fair and you'll never have an issue"). Communications back to them should match — direct, concrete, no enterprise hedging, but with clear evidence of compliance thinking. Don't write like a vendor; write like a builder.
