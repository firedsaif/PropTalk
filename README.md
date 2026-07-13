# PropTalk US

An AI voice agent that answers leasing calls 24/7 for small US property managers — answers listing questions from real data, books tours onto the client's calendar, triages maintenance, takes messages, and emails a summary after every call.

**Wedge:** after-hours / overflow only — "We only take the calls you're already missing."
**Price:** $399/mo · 14-day free pilot · 300-minute cap · 5 showings or you don't pay.

## Start here (docs)

| Doc | What it answers |
|---|---|
| [docs/prd.md](docs/prd.md) | What we're building and why (requirements, users, metrics) |
| [docs/architecture.md](docs/architecture.md) | Tech stack, data model, API, folder structure, flows |
| [docs/rules.md](docs/rules.md) | What to use/avoid, error handling, security, compliance |
| [docs/phases.md](docs/phases.md) | Build order + progress tracker + **money timeline** |
| [docs/PROPTALK_US_BUILD_PLAYBOOK.md](docs/PROPTALK_US_BUILD_PLAYBOOK.md) | The full zero-to-first-client playbook (source) |
| [docs/RETELL_AGENT_CONFIG.md](docs/RETELL_AGENT_CONFIG.md) | Agent system prompt + the 6 tool schemas (source) |

## Build for $0 first

The whole product is built and validated on free tiers before any paid tooling. See [docs/phases.md](docs/phases.md) — Phases 0–4 cost nothing; real spend starts at the demo/outreach stage.

## Secrets

`.env` and everything in `secrets/` are gitignored and must never be committed. Copy [.env.example](.env.example) to `.env` and fill it in. `secrets/twilio-recovery-code.txt` is a credential — keep a copy in a password manager, and rotate it if it's ever been exposed.

## Status

Pre-build — planning docs complete, code not yet scaffolded. Next: Phase 1 (data layer). Track progress in [docs/phases.md](docs/phases.md).
