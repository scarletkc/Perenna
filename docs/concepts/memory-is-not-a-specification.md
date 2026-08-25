# Memory Is Not a Specification

Perenna makes memory durable, portable, and reviewable. Those properties do
not make every memory authoritative.

Memory and project rules serve different purposes:

- memory preserves context that may matter again;
- a specification defines what an agent must do now.

Treating them as interchangeable makes retrieval less useful and project
behavior less reliable.

## Memory is descriptive

Memory records information such as:

- stable user preferences;
- project history and previous implementation attempts;
- decisions and the context in which they were made;
- unresolved issues and observations worth revisiting;
- pointers to current architecture or workflow documents.

This information can guide later work, but it may become stale. Preferences
change, implementations move, and an earlier decision can be superseded.
Perenna therefore supports explicit retrieval and revision instead of loading
every memory into every prompt.

Git history makes a memory auditable. It does not promote an old statement
into a current rule.

## Specifications are normative

Project instructions, architecture documents, API references, contribution
guides, and policies define the current contract. They answer questions such
as:

- Which invariants must remain true?
- Which workflow is required for a repository change?
- Which public schemas and compatibility guarantees apply?
- Which generated files must not be edited directly?
- Which safety checks are mandatory?

These rules must be available deterministically. Their application cannot
depend on whether semantic search happens to retrieve the right passage.

If forgetting a statement could make an agent violate the project contract,
that statement needs a canonical home in the current workspace or governing
configuration. A memory may point to it, but should not be its only home.

## Retrieval is for context, not enforcement

Perenna search returns bounded ranked candidates. It intentionally does not
claim that every result is relevant or that every relevant memory was
returned. That is a useful contract for recall and a weak contract for rules.

Suppose a repository has this invariant:

> Never write directly to the index. Committed Markdown is permanent truth.

If the invariant exists only in memory, the agent may miss it because:

- the task wording is not semantically close enough;
- another result ranks above it;
- the relevant passage falls outside the returned chunk;
- the memory describes a superseded version of the architecture.

Perenna's own invariant therefore lives in the current
[architecture](architecture.md) and project instructions. Memory can help an
agent rediscover that rule, but retrieval does not enforce it.

## Remember decisions without replacing their records

A useful memory can say:

> Active cross-device access uses one HTTP service. See ADR 0001.

The memory helps another agent discover the decision. The
[ADR](../decisions/0001-cross-device-access-and-git-sync.md) remains the
authoritative record of its context, alternatives, consequences, and current
status.

This distinction applies beyond ADRs. A memory can summarize or point to a
release workflow, API rule, or architectural boundary, while the current
runbook, reference, or specification owns the complete rule.

| Concern | Appropriate memory use | Canonical authority |
| --- | --- | --- |
| User preference | Store the current preference | Current user instruction when provided |
| Historical context | Store it directly | Memory and its Git history |
| Previous implementation attempt | Store the result and lesson | Memory and relevant repository history |
| Architectural decision | Store a summary and pointer | Current architecture document or ADR |
| Required workflow | Store a discovery pointer when useful | Current project instructions or runbook |
| API or file-format contract | Store a discovery pointer when useful | Current reference and implementation |
| Permission to publish or deploy | Never infer it from memory | Current explicit authorization |

## Resolve conflicts by current authority

The bundled `perenna-memory` Agent Skill uses this default order inside its
workflow:

```text
Current user instructions
        ↓
Current workspace files and observed runtime state
        ↓
Perenna memory
        ↓
Host-local advisory memory
```

Host and organization policy remain outside Perenna and retain the precedence
defined by that environment. A user may also explicitly assign a different
authority for a particular task.

When current workspace evidence conflicts with a Perenna memory, treat the
memory as potentially stale. Explain a material conflict, follow the current
authority, and revise or retire the memory only when the task authorizes that
write.

Memory also never supplies permission for a new action. Remembering that a
repository was published before does not authorize another push, release,
deployment, or destructive operation.

## Keep memory focused

Separating memory from specifications improves both:

- memories remain concise, relevant context rather than a second copy of the
  repository;
- project rules stay inspectable in their canonical files;
- deterministic reads handle correctness-critical constraints;
- semantic retrieval can focus on history, preferences, and learned context;
- conflicts have an explicit resolution path.

The same principle applies to reference knowledge. A retrieved document can be
useful without being authoritative. Perenna keeps reference knowledge as a
distinct future domain for this reason; see
[ADR 0002](../decisions/0002-separate-memory-and-reference-knowledge.md).

## Rule of thumb

> If forgetting something would be inconvenient, it may belong in memory.

> If forgetting something would make the agent violate the project contract,
> it belongs in the project specification.

Memory provides continuity. Specifications provide correctness. Agents need
both, with the boundary kept explicit.
