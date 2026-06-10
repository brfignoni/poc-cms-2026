---
description: Update any README.md following the project conventions — applies to the root README and all module READMEs inside modules/.
allowed-tools: Read, Edit, Write, Glob, Bash(ls:*), Bash(cat:*)
---

Update the target `README.md` following these rules. Some rules apply everywhere, others only to the root README.

---

## Rules that apply to every README (root and modules)

### Index

Every README must have an index at the top that links to every section using anchor links. Keep it in sync whenever sections are added or removed.

```md
## Index

- [Section name](#section-name)
```

### Dependencies table

If the README is in the same folder as a `package.json`, it must contain a `## Dependencies` section with a table describing what each dependency and devDependency does. Read the `package.json` to get the current list.

- Keep this table in sync whenever `package.json` changes (packages added, removed, or updated).
- One row per package. Plain language — describe what the package does in this project, not just its npm description.
- Split into two tables: **Dependencies** and **Dev dependencies**.

```md
## Dependencies

### Dependencies

| Package       | What it does             |
| ------------- | ------------------------ |
| `example-pkg` | Handles X in production. |

### Dev dependencies

| Package           | What it does                          |
| ----------------- | ------------------------------------- |
| `example-dev-pkg` | Runs Y during development/build only. |
```

---

## Rules that apply to the root README only

### Project structure section

The root README must have a `## Project structure` section listing every module inside `modules/` with:

- The module folder name
- A one-line description of what it is for
- A link to its own README

To get the current list of modules run: `ls modules/`

**Do not describe modules in detail here** — that belongs in each module's own README. One sentence max per entry.

```md
## Project structure

| Module            | Description                                                      |                                     |
| ----------------- | ---------------------------------------------------------------- | ----------------------------------- |
| `modules/cms`     | Strapi headless CMS — content API and admin panel.               | [README](modules/cms/README.md)     |
| `modules/web`     | Astro frontend — web component library and public site.          | [README](modules/web/README.md)     |
| `modules/crawler` | Legacy site crawler — scrapes and exports content for migration. | [README](modules/crawler/README.md) |
```

- Keep this table in sync with the actual state of `modules/`.
- If a module does not have a README yet, omit the link but still list the module.
- The root README is an **overview** — do not duplicate content that lives in a module README.
