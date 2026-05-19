---
name: clean-code
description: Use always; especially when touching legacy code. Keeps code easy to read, change, and test.
---

# CleanCode

## Purpose

Keep code easy to read, change, and test.

## When to Use

Always; especially when touching legacy code.

## Instructions

- Name things by domain; keep functions small; avoid hidden side effects; inject dependencies.
- Write tests first for risky code; add contracts at boundaries; avoid duplicate logic.
- Keep PRs small and cohesive; document decisions in code and ADRs.

## Heuristics

- If a function exceeds ~20–30 lines or 2 responsibilities, split it.

## Examples

Refactor complex conditional into strategy pattern with tests.
