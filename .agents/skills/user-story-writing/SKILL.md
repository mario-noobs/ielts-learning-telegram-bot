---
name: user-story-writing
description: Use during backlog grooming or refinement. Writes actionable, testable user stories with acceptance criteria and a metric.
---

# UserStoryWriting

## Purpose

Write actionable, testable user stories.

## When to Use

Backlog grooming, refinement.

## Instructions

- State user, need, value, acceptance criteria, metric, DoR/DoD (see `CHECKLISTS.md`).

## Heuristics

- No story without acceptance criteria and metric.

## Examples

`[GIT][Brazil] Round WTH taxes on client invoices

Description

As an accounting user,
When client invoices are generated for Brazilian entities,
I want the withholding tax (WHT) amounts to be rounded up,
So that there are no discrepancies (e.g. 0.01 gaps) in accounting entries.

Business Rules
Applies to client invoices for Brazilian entities only.

WHT amounts must always be rounded up.

The rounding must prevent any difference between invoice totals and accounting entries.

Acceptance Criteria
✅ AC1 – WHT rounded up
Given a client invoice includes WHT,
When the tax amount is calculated,
Then the WHT amount is rounded up.

✅ AC2 – No rounding discrepancies
Given the invoice is generated,
Then there is no 0.01 difference between invoice and accounting entries.`
