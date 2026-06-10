# poc-cms-2026

Monorepo — Strapi CMS, Astro web components, and a legacy site crawler.

## Index

- [Project structure](#project-structure)
- [Dependencies](#dependencies)
- [Git conventions](#git-conventions)
  - [Branch names](#branch-names)
  - [Commit messages](#commit-messages)

---

## Project structure

| Module            | Description                                                      |        |
| ----------------- | ---------------------------------------------------------------- | ------ |
| `modules/cms`     | Strapi headless CMS — content API and admin panel.               | README |
| `modules/web`     | Astro frontend — web component library and public site.          | README |
| `modules/crawler` | Legacy site crawler — scrapes and exports content for migration. | README |

---

## Dependencies

### Dev dependencies

| Package                           | What it does                                                                        |
| --------------------------------- | ----------------------------------------------------------------------------------- |
| `husky`                           | Runs git hooks (commit-msg, pre-commit, pre-push) to enforce conventions locally.   |
| `@commitlint/cli`                 | Validates commit messages against the rules in `commitlint.config.mjs`.             |
| `@commitlint/config-conventional` | Base ruleset for Conventional Commits that `commitlint` extends.                    |
| `lint-staged`                     | Runs Prettier only on staged files before each commit, keeping the diff clean.      |
| `prettier`                        | Code formatter — applied by `lint-staged` on JS, TS, CSS, JSON, and Markdown files. |

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
