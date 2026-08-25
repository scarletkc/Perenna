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
- recurring problems, durable open questions, and observations worth revisiting;
- pointers to current architecture or workflow documents.

This information can guide later work, but it may become stale. Preferences
change, implementations move, and an earlier decision can be superseded.
Perenna therefore supports explicit retrieval and revision instead of loading
every memory into every prompt.

Git history makes a memory auditable. It does not promote an old statement
into a current rule.

Revisable does not mean short-lived. Active task progress, temporary deployment
state, transient debugging results, and other rapidly expiring facts belong in
the current task, issue tracker, workspace, or runtime diagnostics. A permanent
memory should have expected value beyond the current session even when it may
need a later correction.

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
that statement needs a canonical home in a designated project instruction
file, canonical document, or governing configuration validated for the current
environment. A memory may point to it, but should not be its only home.

For Perenna, [`AGENTS.md`](../../AGENTS.md) and the
[contributing guide](../development/contributing.md) identify the applicable
rules and the documents that own each contract. Do not promote an arbitrary
workspace file or configuration value to authority merely because it exists.

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

| Concern | Memory use | Authority |
| --- | --- | --- |
| User preference | Store it | Current instruction |
| Historical context | Store it directly | Memory and its Git history |
| Previous attempt | Store the lesson | Repository history |
| Architecture | Summary and pointer | Current document or ADR |
| Required workflow | Discovery pointer | Project instructions or runbook |
| API or file format | Discovery pointer | Reference and implementation |
| Publish or deploy permission | Never infer it | Explicit authorization |

## Resolve conflicts by current authority

The bundled `perenna-memory` Agent Skill uses this default order inside its
workflow:

```text
Current user instructions
        ↓
Designated project instructions, canonical documents,
and validated current runtime evidence
        ↓
Perenna memory
        ↓
Host-local advisory memory
```

Host and organization policy remain outside Perenna and retain the precedence
defined by that environment. A user may also explicitly assign a different
authority for a particular task.

Sources in the shared project tier establish different kinds of claims:
designated instructions and canonical documents define the project contract,
while validated runtime evidence establishes current state. Apply each source
only to claims it can establish instead of treating either category as a
blanket override.

Runtime observations count as current evidence only after their environment,
identity, and relevance to the task have been verified. When a designated
current source or validated runtime observation conflicts with a Perenna
memory, treat the memory as potentially stale. Explain a material conflict,
follow the current authority, and revise or retire the memory only when the
task authorizes that write.

Validated runtime evidence establishes current state only. It does not
authorize publishing, release, deployment, destructive operations, or other
consequential actions; those require separate current authorization.

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
>
> If forgetting something would make the agent violate the project contract,
> it belongs in the project specification.

Memory provides continuity. Specifications provide correctness. Agents need
both, with the boundary kept explicit.
