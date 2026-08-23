# Curating Memories

Use this guide before creating, changing, or deleting permanent memory.

## Decide what is durable

Use `memory_write` only for information likely to remain useful in another
session:

- stable user preferences and collaboration boundaries;
- long-lived project constraints and architectural decisions;
- verified recovery procedures and recurring workflows;
- concise lessons whose cause and remedy are not obvious from current files.

Treat feedback as source material: store it only after converting a durable,
reusable correction into the preference, constraint, workflow, or lesson it
changes; do not preserve feedback as an event or category.

Do not turn ordinary task completion into a routine write. Do not store:

- passwords, API keys, tokens, private keys, or other credentials;
- private system prompts, identity seeds, or sensitive source material;
- raw conversations, chain-of-thought, or copied logs;
- temporary progress, current task status, or speculative debugging notes;
- volatile runtime facts that should be checked live;
- facts already clear from the current repository or canonical documentation;
- unapproved ideas presented as decisions, plans, or commitments.

Before creating a memory, list or search for the subject so the update does not
create a duplicate.

## Choose scope and content

Use global scope for preferences or constraints that apply across projects.
Use project scope for repository-specific architecture, history, policy, and
workflows. Prefer a stable project slug already present in the index.

Write the final reusable state:

- a specific, durable title;
- a one-sentence summary describing what the memory covers, not a snapshot of
  its current details;
- a body containing the decision, constraint, evidence, and recovery details
  another agent would actually need.

Do not narrate abandoned attempts or the conversation that produced the final
state unless that history is itself necessary to avoid a repeated failure.

## Create or update safely

Create only after checking that the scope has no existing memory for the same
subject. For an existing memory, use the current ID and revision returned by
`get` or `search`.

- Prefer `patch` for exact local changes. Preserve unrelated content.
- Use `replace` only when the complete memory genuinely needs restructuring.
- If a revision is stale or an exact patch anchor no longer matches, re-read
  the memory and reconcile the new state. Never force or approximate the edit.
- Update the summary only when the subject covered by the memory changes.

## Forget deliberately

Use `memory_delete` only when the user clearly intends to forget the complete
subject. Read the current memory first and pass its exact ID, title, and
revision. Deletion removes it from current recall but does not purge older
local or remote Git history; disclose that boundary when sensitive deletion is
requested.

After any mutation, report the affected memory title and scope, whether the
local write was committed, and any non-synchronized `sync_status`. Do not echo
sensitive or unnecessarily complete memory content in the response.
