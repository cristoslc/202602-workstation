# AGENTS.md

## Skill routing

When the user wants to create, plan, write, update, transition, or review any documentation artifact (Vision, Journey, Epic, Story, Agent Spec, Spike, ADR, Persona, Runbook, Bug) or their supporting docs (architecture overviews, competitive analyses, journey maps), **always invoke the spec-management skill**. This includes requests like "write a spec", "let's plan the next feature", "create an ADR for this decision", "move the spike to Active", "add a user story", "create a runbook", "file a bug", or "update the architecture overview." The skill contains the artifact types, lifecycle phases, folder structure conventions, relationship rules, and validation procedures — do not improvise artifact creation outside the skill.

**For all task tracking and execution progress**, use the **execution-tracking** skill instead of any built-in todo or task system. This applies whether tasks originate from spec-management (implementation plans) or from standalone work. The execution-tracking skill bootstraps and operates the external task backend — it will install the CLI if missing, manage fallback if installation fails, and translate abstract operations (create plan, add task, set dependency) into concrete commands. Do not use built-in agent todos when this skill is available.

## Pre-implementation protocol (MANDATORY)

Implementation of any SPEC artifact (Epic, Story, Agent Spec, Spike) requires an execution-tracking plan **before** writing code. Invoke the spec-management skill — it enforces the full workflow.

## Issue Tracking

This project uses **bd (beads)** for all issue tracking. Do NOT use markdown TODOs or task lists. Invoke the **execution-tracking** skill for all bd operations — it provides the full command reference and workflow.

