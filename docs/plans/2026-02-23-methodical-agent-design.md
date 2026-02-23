# Methodical Agent Behavior — System Instruction Update

**Date:** 2026-02-23
**Status:** Approved

## Problem

The agent executes immediately on every request, regardless of complexity. For multi-step or ambiguous tasks, it jumps straight to tool calls without clarifying intent or presenting a plan. This leads to wasted work and results that miss the user's actual goal.

## Solution

Update `self.system_instruction` in `agents.py` to teach the agent a clarify-plan-execute workflow for complex tasks. No code changes — only the instruction text changes.

## Task Classification

**Simple tasks** (act immediately, current behavior):
- Single-step operations with clear intent
- Direct questions, file reads, single file edits
- Tasks requiring fewer than 3 tool calls with no ambiguity

**Complex tasks** (clarify, plan, then execute):
- Multi-step tasks requiring 3+ tool calls
- Ambiguous scope or approach
- Tasks touching multiple files or requiring architectural decisions

## Complex Task Workflow

**Phase 1 — Clarify (1-3 questions):**
- Respond with text only (no tool calls)
- Ask ONE focused question per response
- Move to Phase 2 once enough context is gathered
- Skip if user says "just do it"

**Phase 2 — Plan:**
- Present a numbered plan in text (no tool calls)
- End with "Ready to proceed?"
- Wait for user confirmation

**Phase 3 — Execute:**
- Call tools step by step (existing dry-run/approval flow)
- Report progress after each major step

## Changes

**File:** `agents.py` — `self.system_instruction` (lines 3763-3791)

**What changes:**
- Rule 10 gets a qualifier: "do not ask for permission" applies to simple tasks only
- Add Rule 17: Task classification logic
- Add Rule 18: Complex task protocol (clarify → plan → execute)
- Add Rule 19: Progress reporting after each plan step

**What does NOT change:**
- Rules 1-9, 11-16 (untouched)
- `agents.py` code (no functions, classes, or graph changes)
- `tui.py` (no changes)
- `chat_once()`, `execute_dry_run()`, LangGraph (no changes)

## Why This Works

The TUI conversation loop already supports multi-turn dialogue. When `chat_once` returns `status: "success"` with text (no tool calls), the user sees it and replies. The agent just needs to be instructed to use text responses for clarification and planning before jumping to tools.
