# ADR 0002: Separate memory from reference knowledge

Status: Accepted

This record accepts a direction for future work. It does not describe a
currently implemented knowledge-base feature or public API.

## Context

Perenna currently stores curated memories: durable preferences, facts,
decisions, and learned context that an agent should carry between sessions.
These entries are intentionally small enough to review and revise as the user
or project changes.

Agents also need access to larger reference material such as project notes,
technical documentation, and design records. That material benefits from the
same properties as memory: portable files, Git history, semantic retrieval,
and a derived index that can be rebuilt. It has a different meaning and
lifecycle, however. A document is a source to consult, not a fact the agent is
expected to remember about its user or prior work.

Treating both kinds of context as memories would make curation rules,
mutations, and search results ambiguous. Building an independent retrieval
platform would instead duplicate Perenna's existing storage and indexing
boundaries.

## Decision

Add reference knowledge as a distinct Perenna domain when knowledge-base work
begins. Preserve this semantic boundary even where the two domains reuse
infrastructure.

| Domain | Primary question | Typical content | Lifecycle |
| --- | --- | --- | --- |
| Memory | What should the agent remember? | User preferences, durable facts, decisions, and learned context | Small, curated entries that may be revised as understanding changes |
| Knowledge | What source material can the agent consult? | Documents, project material, technical references, and notes | Larger, collection-oriented sources that are relatively stable |

Both domains may reuse these architectural primitives:

- portable Markdown or text files as permanent truth;
- Git history for durability, auditability, and recovery;
- deterministic chunking and trusted metadata;
- Vexor as a rebuildable retrieval index rather than a second store;
- existing local and self-hosted MCP transport boundaries where they remain
  applicable.

Knowledge operations will remain separate from the existing memory tools.
Names such as `knowledge_list`, `knowledge_search`, `knowledge_get`, and
`knowledge_add` illustrate the intended shape, but this ADR does not fix their
schemas or final names. A later API design must preserve strict validation and
must not turn `memory_read`, `memory_write`, or `memory_delete` into generic
context operations.

Ship a separate `perenna-knowledge` Agent Skill with the first public
knowledge operations. It will teach clients when to use knowledge instead of
memory, how to select a collection, how to search before getting a complete
source, and how to keep answers grounded in that source. The Skill must
describe only tools that are actually available, must not simulate missing
knowledge operations, and must not promote reference documents into memories
without separate authority for a memory write.

Memory and knowledge may refer to each other through stable, typed references
instead of duplicating content. A link such as
`knowledge://perenna/design/architecture` is illustrative; the identifier and
metadata contract remain to be designed. Retrieval stays explicit: an agent
may query either domain or combine both results, but Perenna will not silently
blend every memory and document search.

This ADR does not choose whether memory and knowledge use separate roots in one
Git repository or separate repositories. Either layout can preserve the
decision. The implementation design must select one after defining the
required transaction, synchronization, backup, and indexing boundaries.

## First delivery boundary

The first knowledge-base delivery should be the smallest complete document
retrieval workflow:

- UTF-8 Markdown and plain-text documents only;
- explicit collections for grouping documents;
- add, list, search, and full-document get operations;
- bounded chunking, metadata validation, and a rebuildable Vexor index;
- Git-native permanent storage with failures kept visible.

It will not include PDF or other binary ingestion, OCR, HTML extraction, web
crawling, automatic repository ingestion, automatic summarization, pluggable
chunking pipelines, provider orchestration, a permissions system, multi-user
storage, or a general-purpose RAG framework. Those capabilities require
observed use cases and separate decisions.

The existing memory model, file format, and three-tool MCP contract remain
unchanged until an implementation explicitly changes their canonical
documentation and code.

## Consequences

- Perenna can grow into one portable context store without making documents
  pretend to be memories.
- Memory retrieval remains focused on durable context about the user, agent,
  and prior work; knowledge retrieval remains focused on source material about
  a topic.
- Storage, Git, and retrieval infrastructure can be reused, but domain models,
  validation, result shapes, and index namespaces may remain separate.
- Clients that need both kinds of context may perform two explicit searches
  and decide how to combine the results.
- Exact storage layout, API schemas, mutation semantics, and typed-link format
  require follow-up design before implementation.

## Rejected alternatives

### Store reference documents as memories

This would reuse the current API immediately, but it would mix two different
curation and retrieval contracts. Large, stable sources would compete with
small, evolving memories, and memory mutations would acquire document-management
semantics they were not designed to carry.

### Build a general-purpose RAG platform

Supporting every source format, ingestion connector, chunking strategy,
embedding provider, and permissions model would move Perenna away from its
local-first, portable context boundary before a concrete need justified the
complexity.

### Build knowledge as an unrelated product

This would preserve semantic separation but duplicate the Git, file safety,
transport, and rebuildable-index principles that already fit the problem.
Separate domains inside Perenna provide the useful boundary without requiring
two unrelated systems.

## Revisit criteria

Reconsider this decision if observed usage shows that memory and reference
documents have the same curation, mutation, and retrieval lifecycle. Revisit
the first-delivery boundary when real workflows require non-text sources or
additional ingestion, and make those expansions through focused decisions
rather than an open-ended RAG abstraction.
