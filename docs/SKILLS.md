# Instruction skills

`/skills` manages global, account-owned chat skills and project skills. Skills
are Markdown instructions, not executable code, tools or permission grants.
They pass through the same outbound privacy review as other task context.

## Format

```markdown
---
name: Evidence report
description: Summarize supplied observations.
parameters: {"tone":{"type":"string","default":"concise"}}
---
Write in a {{tone}} style. Cite supplied evidence and distinguish assumptions.
```

Frontmatter accepts only `name`, `description` and a one-line JSON `parameters`
object. General YAML execution/tags are not supported. Up to 12 parameters use
string, number or boolean types with a required matching default. Values are
bounded to 1000 characters and substituted once. Prototype keys, unknown value
keys and type mismatches fail validation. The editor includes Markdown preview;
chat/project selectors expose parameter overrides before submission.

Instructions are 10–6000 characters, name 2–80 and description at most 300.
A document is bounded to 12,000 characters and API input to 64KiB. Up to three
active versions can be selected. At most 50 records, including version history,
are retained per project or global account scope.

## Lifecycle and authorization

Creating saves a draft. Editing creates a new immutable version, linked by
family ID and incremented version. The previous record is not overwritten.
Activation checks the exact content digest and retires another active version
in the same family. Deactivation retires a version. Global skills are editable
and activatable only by their account owner. Project editors can draft; platform
owners review project activation. Read-only accounts cannot write or activate.

The chat request sends selected IDs and optional `skillParameters`, keyed by
version ID. The server revalidates scope, active status and parameter types,
then includes rendered instructions in task guidance. It does not elevate them
to privileged policy. The selected instructions are part of the reviewed privacy
snapshot and durable job payload. Deactivating after enqueue does not rewrite an
already reviewed job; cancel that job if the embedded guidance must not execute.
There is no arbitrary script installation or third-party skill marketplace.
