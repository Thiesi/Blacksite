# Claude Code guidance

Read and follow `AGENTS.md` as the canonical project guidance for
Blacksite. It covers the canon hierarchy, the slice workflow, coding and
testing rules, and how this repository relates to NetBBS.

Add material here only when it is specific to Claude Code and does not
apply to other development agents.

- Work in a git worktree, never in a checkout another session may be
  using.
- When a slice names a different primary model than the one you are
  running as, say so in the PR description.
