---
name: system-design
description: Use when introducing new services, data stores, or cross-cutting concerns. Creates resilient, maintainable systems with clear boundaries and observability.
---

# SystemDesign

## Purpose

Create resilient, maintainable systems with clear boundaries and observability.

## When to Use

When introducing new services, data stores, or cross-cutting concerns.

## Instructions

- Define domain boundaries and contracts; choose boring tech that fits skills.
- Model data and flows; avoid long-running transactions; add idempotency and retries for I/O.
- Plan observability: logs, metrics, traces; define SLOs and error budgets.

## Heuristics

- Prefer asynchronous integration for non-critical paths; keep modules small and cohesive.

## Examples

ADR choosing event-driven integration with dead-letter queue and observability plan.
