# SKY NET paired project-update transaction

`project_update` is an atomic paired promotion across the configured Automation and Cybersecurity repositories.

1. Preflight every configured repository before mutating either.
2. Require a clean worktree and an existing upstream branch.
3. Permit only unchanged or fast-forward states.
4. Reject local-ahead and diverged histories.
5. Promote sequentially with `git merge --ff-only`.
6. If any later promotion fails, roll back prior promotions only when their current HEAD still equals the commit SKY NET just applied.
7. Record the result in the append-only audit chain.

This prevents one project from silently advancing while its paired project remains on an incompatible revision.
