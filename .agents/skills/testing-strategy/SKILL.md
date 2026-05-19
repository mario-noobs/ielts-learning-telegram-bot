---
name: testing-strategy
description: Use when planning and implementing tests across pyramid layers. Ensures fast, reliable feedback and risk coverage.
---

# TestingStrategy

## Purpose

Ensure fast, reliable feedback and risk coverage.

## When to Use

Planning and implementing tests across pyramid layers.

## Instructions

- Identify critical paths and failure modes; select the cheapest reliable test level.
- Create API contracts; write unit tests for pure logic; integration tests for boundaries; minimal e2e.
- Add production checks: dashboards, alerts, and sampling of real traffic where safe.

## Heuristics

- Prefer deterministic tests; cap mocks; stabilize locators via data-test-id or role.

## Examples

Pyramid with 70% unit, 25% integration, 5% e2e on critical flows.
