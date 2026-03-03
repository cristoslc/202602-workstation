# Global Claude Instructions

## Constraints

No interactive commands, no emoji in filenames, no fabricated tool names, always use non-interactive flags (-f, --no-pager, yes |). If you're unsure about a tool or path, ask me first.

When a tool or service is reported as broken, do NOT attempt to use that same tool to diagnose the problem. Use alternative diagnostic approaches (logs, config inspection, API calls, etc.).

## Habits

Use an agent when performing git commits and pushes, to keep the main thread clean and unblocked. When the commit involves domain-specific conventions (e.g., lifecycle hash stamping, index refresh steps, phase transition workflows), include the relevant convention text verbatim in the agent prompt — agents do not have access to skill instructions or AGENTS.md unless explicitly provided.


## Locations

### Personal Code Projects

Personal code projects live in `~/Documents/code/`. When looking for source repos for skills, tools, or other personal projects, check there first.

Examples:
- `~/Documents/code/media-summary/` — the media-summary Claude skill
