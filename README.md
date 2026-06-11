# poc-cms-2026

Monorepo — Strapi CMS, Astro web components, and a legacy site crawler.

## Index

- [Project structure](#project-structure)
- [Repo configuration](#repo-configuration)
  - [Corepack](#corepack)
  - [ESLint](#eslint)
  - [EditorConfig](#editorconfig)
  - [Prettier](#prettier)
  - [Engine enforcement](#engine-enforcement)
  - [TypeScript](#typescript)
  - [Pre-push checks](#pre-push-checks)
  - [CI workflow](#ci-workflow)
  - [Dependabot](#dependabot)
- [Dependencies](#dependencies)
  - [Dev dependencies](#dev-dependencies)
- [Linting](#linting)
- [Git conventions](#git-conventions)
  - [Branch names](#branch-names)
  - [Commit messages](#commit-messages)

---

## Project structure

| Module            | Description                                                      |                                     |
| ----------------- | ---------------------------------------------------------------- | ----------------------------------- |
| `modules/crawler` | Legacy site crawler — scrapes and exports content for migration. | [README](modules/crawler/README.md) |

---

## Repo configuration

| File / field                       | What it does                                                                                                              |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `.nvmrc`                           | Pins the Node.js version. Version managers (nvm, fnm, volta) read this to auto-switch on `cd`.                            |
| `packageManager` in `package.json` | Declares the exact pnpm version. [Corepack](#corepack) uses this to install the right version and block others.           |
| `eslint.config.mjs`                | [ESLint](#eslint) flat config (v9). Defines linting rules for the entire repo. Modules inherit this config automatically. |
| `.editorconfig`                    | [EditorConfig](#editorconfig) — sets basic editor behavior (indentation, line endings) so every editor agrees.            |
| `.prettierrc`                      | [Prettier](#prettier) config — explicit formatting rules (quotes, semicolons, line width).                                |
| `.prettierignore`                  | Tells Prettier which files to skip (lockfiles, build output, etc.).                                                       |
| `engines` in `package.json`        | [Engine enforcement](#engine-enforcement) — declares the minimum Node.js and pnpm versions required.                      |
| `tsconfig.json`                    | [TypeScript](#typescript) base config. Modules extend this so they all share the same compiler settings.                  |
| `.github/workflows/ci.yml`         | [CI workflow](#ci-workflow) — runs lint, typecheck, and tests on every pull request.                                      |
| `.github/dependabot.yml`           | [Dependabot](#dependabot) config — automated PRs for dependency and GitHub Actions updates.                               |

### Corepack

Corepack is a tool that ships with Node.js. It reads the `packageManager` field in `package.json` and ensures every contributor uses the exact same package manager and version. If someone tries to run `npm install` or a different pnpm version, Corepack will block it. This prevents lockfile drift and dependency resolution mismatches across machines.

### ESLint

ESLint is a static analysis tool (linter) for JavaScript and TypeScript. Unlike Prettier, which only handles formatting (spacing, semicolons, line length), ESLint analyzes what the code **does** and catches actual bugs — unused variables, unreachable code, references to undefined variables, duplicate object keys, invalid regex, and more. It runs automatically on staged files during each commit and can also be run manually with `pnpm lint`.

### EditorConfig

Different editors have different default settings — VS Code might use 4-space indentation while another uses tabs, one might use Windows line endings (`\r\n`) while another uses Unix (`\n`). `.editorconfig` is a standard file that sets the basics: indent style, indent size, line endings, charset, and trailing whitespace.

Two things read it:

1. **Your editor** — JetBrains IDEs (WebStorm, IntelliJ) have built-in support. VS Code needs the [EditorConfig extension](https://marketplace.visualstudio.com/items?itemName=EditorConfig.EditorConfig). The editor applies these settings in real time as you type, so new lines are already formatted correctly.
2. **Prettier** — since v2, Prettier reads `.editorconfig` automatically and uses its values (indent size, line endings) as defaults. This means both your editor and Prettier agree without duplicating config.

### Prettier

Prettier is an opinionated code formatter. It rewrites your code to follow a consistent style — things like whether to use single or double quotes, where to break long lines, trailing commas, etc. The `.prettierrc` file makes those choices explicit so they don't change if Prettier updates its defaults. The `.prettierignore` file tells Prettier to skip files that shouldn't be formatted, like the lockfile or build output.

### Engine enforcement

The `engines` field in `package.json` declares which versions of Node.js and pnpm this repo supports. On its own it's just a warning — but combined with `engine-strict=true` in `.npmrc`, pnpm will **refuse to install** if the contributor's Node or pnpm version is too old. This catches version mismatches early instead of letting them cause mysterious build failures later.

### TypeScript

TypeScript adds static types to JavaScript. Instead of discovering that a variable is the wrong type at runtime (when a user hits a bug), TypeScript catches it at build time while you're still writing code. The root `tsconfig.json` defines shared compiler settings (how strict the checks are, which JS version to target, how modules are resolved). When you add a TS module, it extends this base config with `"extends": "../../tsconfig.json"` in its own `tsconfig.json`, so every module follows the same rules without duplicating config.

The `typecheck` script (`pnpm typecheck`) runs `tsc --noEmit` recursively across all modules that define a `typecheck` script. It checks types without producing output files — just tells you if anything is wrong.

### Pre-push checks

The `pre-push` git hook runs automatically every time you `git push`. It acts as a final safety net before code leaves your machine. In this repo it runs two things:

1. **Branch name validation** — rejects pushes from branches that don't follow the naming convention (e.g. `feat/something`).
2. **`pnpm check`** — runs ESLint and TypeScript type-checking across all modules. If any linting error or type error exists, the push is blocked until you fix it.

This means broken code can't reach the remote repository by accident. You'll see the errors in your terminal and can fix them before pushing again.

### CI workflow

The pre-push hook protects you locally, but someone can skip it with `git push --no-verify`. The CI workflow (`.github/workflows/ci.yml`) is the server-side safety net — it runs on every pull request targeting `main` and executes the same checks: install dependencies, lint, typecheck, and test. If any step fails, the PR gets a red check and can't be merged (if you enable branch protection rules in GitHub). This guarantees that `main` always has clean, passing code regardless of what individual contributors do locally.

### Dependabot

Dependabot is a GitHub feature that monitors your dependencies for new versions and security vulnerabilities. When it finds an update, it automatically opens a pull request with the version bump already done. You just review and merge. The config groups dev dependencies together so you don't get a separate PR for every single package. It also watches for GitHub Actions updates (e.g. `actions/checkout@v4` → `v5`), so your CI workflows stay current too. It runs weekly to avoid being noisy.

---

## Dependencies

### Dev dependencies

| Package                           | What it does                                                                                   |
| --------------------------------- | ---------------------------------------------------------------------------------------------- |
| `eslint`                          | Static analysis / linter — catches unused variables, unreachable code, and other bugs.         |
| `@eslint/js`                      | ESLint's official recommended ruleset for JavaScript.                                          |
| `typescript-eslint`               | Connects ESLint to TypeScript — catches type-aware bugs like unsafe `any` and missing `await`. |
| `globals`                         | Provides environment-specific global variable definitions for ESLint (`process`, `window`).    |
| `husky`                           | Runs git hooks (commit-msg, pre-commit, pre-push) to enforce conventions locally.              |
| `@commitlint/cli`                 | Validates commit messages against the rules in `commitlint.config.mjs`.                        |
| `@commitlint/config-conventional` | Base ruleset for Conventional Commits that `commitlint` extends.                               |
| `lint-staged`                     | Runs ESLint and Prettier on staged files before each commit, keeping the diff clean.           |
| `prettier`                        | Code formatter — applied by `lint-staged` on JS, TS, CSS, JSON, and Markdown files.            |
| `typescript`                      | TypeScript compiler — adds static type checking to JavaScript. Used via `pnpm typecheck`.      |

---

## Linting

Run ESLint across the entire repo:

```bash
pnpm lint
```

ESLint also runs automatically on staged files during each commit via `lint-staged`.

The configuration lives in `eslint.config.mjs` (ESLint v9 flat config).

---

## Git conventions

### Branch names

Format: `type/short-description`

| Type       | When to use                          |
| ---------- | ------------------------------------ |
| `feat`     | New feature or page                  |
| `fix`      | Bug fix                              |
| `chore`    | Maintenance, dependencies, config    |
| `docs`     | Documentation only                   |
| `refactor` | Code restructure, no behavior change |
| `style`    | CSS / formatting only                |
| `test`     | Adding or fixing tests               |
| `perf`     | Performance improvement              |
| `ci`       | CI/CD changes                        |
| `build`    | Build system changes                 |
| `hotfix`   | Urgent production fix                |
| `revert`   | Reverting a previous commit          |

Rules for the description part:

- Lowercase only
- Use dashes, no spaces
- 3 to 50 characters

```
✓ feat/hero-section
✓ fix/cms-slug-query
✓ chore/upgrade-astro
✗ my-feature          → missing type/
✗ feat/MyFeature      → not lowercase
✗ feature/foo         → use 'feat', not 'feature'
```

---

### Commit messages

Format: `type(scope): short description`

The scope is **required** and should indicate which module or area changed.

Common scopes: `web`, `cms`, `crawler`, `deps`, `ci`, `docs`

The description must:

- Be lowercase (no sentence case, no ALL CAPS)
- Not end with a period
- Be under 100 characters

```
✓ feat(web): add hero section
✓ fix(cms): resolve slug query issue
✓ chore(deps): upgrade astro to v5
✗ feat: add hero section    → missing scope
✗ Added hero section        → no type or scope
✗ Feat(Web): Hero Section.  → uppercase + period
```
