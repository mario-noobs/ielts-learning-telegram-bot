---
name: release-management
description: Use for every release. Ships safely with staged rollouts, feature flags, and auto-rollback on error.
---

# ReleaseManagement

## Purpose

Ship safely with staged rollouts and feature flags.

## When to Use

Every release.

## Instructions

- Use flags, rollout 10→50→100%, monitor metrics, auto-rollback on error.

## Heuristics

- Never big-bang; always have rollback.

## Examples

Release new feature to 10% of users, monitor, then expand.
