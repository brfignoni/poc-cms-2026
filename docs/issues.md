# Known Issues

## Index

1. [pnpm pre-commit hook fails in Cursor/VS Code GUI](#1-pnpm-pre-commit-hook-fails-in-cursorvs-code-gui)

---

## 1. pnpm pre-commit hook fails in Cursor/VS Code GUI

**Status:** Open (workaround available)

**Error:**

```
[ERR_PNPM_ABORTED_REMOVE_MODULES_DIR_NO_TTY] Aborted removal of modules directory due to no TTY
```

**Cause:**

When committing via the IDE's source control GUI (e.g., Cursor or VS Code), the git hook runs without a **TTY**. TTY stands for **teletypewriter** — it refers to a terminal interface that supports interactive input/output (displaying prompts and reading user keystrokes). When there is no TTY, programs cannot ask interactive questions and must either use defaults or abort.

pnpm's `runDepsStatusCheck` automatically runs `pnpm install` before executing `pnpm exec lint-staged`. When `pnpm install` detects that `node_modules` needs to be purged and rebuilt, it tries to ask for confirmation — but since the IDE's GUI runs hooks as a background process with no TTY attached, it aborts.

The most likely root cause is that the IDE resolves to a **different pnpm or node version** than the terminal shell. That different pnpm version sees `node_modules` was created by another version and wants to purge and rebuild it. When committing from the terminal, the same pnpm version that created `node_modules` is used, so no purge is needed and the check passes silently.

**Workaround:**

Commit from the terminal instead of the IDE's source control GUI:

```bash
git commit -m "your message"
```
