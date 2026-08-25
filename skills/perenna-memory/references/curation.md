# Curating Memories

Use this guide before creating, changing, or deleting permanent memory.

## Decide what is durable

Use `memory_write` only for information likely to remain useful in another
session:

- stable user preferences and collaboration boundaries;
- durable project history, decision context, and previous outcomes;
- concise advisory pointers that help locate a designated canonical project
  rule, procedure, or workflow without duplicating its contract; validate the
  destination independently before relying on it;
- concise lessons whose cause and remedy are not obvious from current files.

Treat feedback as source material: store it only after converting a durable,
reusable correction into the preference, context, workflow insight, or lesson
it changes; do not preserve feedback as an event or category.

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

Use global scope for preferences or durable context that applies across
projects.
Use project scope for repository-specific history, preferences, lessons, and
advisory discovery pointers to current architecture, policy, and workflows.
Validate a pointer's destination as a designated canonical source before
relying on it. Prefer a stable project slug already present in the index.

Group related durable statements into one memory when they form one coherent
subject. Do not create a separate memory for every atomic fact, and do not
combine unrelated subjects merely to reduce the number of memories.

Write the final reusable state:

- a specific, durable title;
- a one-sentence summary describing what the memory covers, not a snapshot of
  its current details;
- a body containing the context, evidence, lessons, and recovery details
  another agent would actually need, with advisory pointers to designated
  authority where applicable. A later reader must validate the target before
  relying on it.

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

## Consolidate overlapping memories

When the user asks to organize, deduplicate, merge, or clean up memories, use
the existing MCP tools instead of inventing a background process or bypassing
the memory contract.

Start with a read-only audit. Use `memory_read` with `list` to inspect titles,
scopes, and summaries. For a store-wide request, enumerate the global index and
each available project, counting the global references only once. Shortlist
plausible overlaps before using `get`; do not load every complete body unless
the collection is small or the user explicitly requests an exhaustive audit.

Compare memories within the same scope by default. Similar global and project
memories may intentionally express a cross-project rule and a project-specific
exception. Report cross-scope overlap separately rather than proposing an
automatic merge.

Read every shortlisted memory completely and classify the relationship before
proposing a change:

- duplicate: the durable meaning is already preserved elsewhere;
- overlap: the memories share material but each contains useful content;
- conflict: their current claims cannot both be applied safely;
- supersession: one memory clearly replaces an older rule or state;
- distinct: the similarity does not justify a change.

The initial cleanup request authorizes this read-only analysis, not an
irreversible choice about which durable wording or identity to keep, unless the
user explicitly authorizes the concrete mutations in the same request. Present
a concise plan naming each affected title and scope, the memory to retain, the
resulting coverage, and every proposed patch, replacement, or deletion. Do not
store the audit report as permanent memory.

After approval, get every affected memory again and use its current revision.
If any revision or exact patch anchor changed, stop that consolidation group,
re-read it, and revise the plan instead of forcing the old proposal. Merge
useful content into the retained memory successfully before deleting a
redundant memory. Treat each mutation result independently: a committed merge
followed by a failed deletion is a partial outcome to report, not a reason to
repeat the merge.

## Forget deliberately

Use `memory_delete` only when the user clearly intends to forget the complete
subject. Read the current memory first and pass its exact ID, title, and
revision. Deletion removes it from current recall but does not purge older
local or remote Git history; disclose that boundary when sensitive deletion is
requested.

After any mutation, report the affected memory title and scope, whether the
local write was committed, and any non-synchronized `sync_status`. Do not echo
sensitive or unnecessarily complete memory content in the response.
