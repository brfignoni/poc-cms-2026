# Strapi - Decisions & Notes

<!-- Notes and decisions related to Strapi for this project. -->

## Index

- [Docker](#docker)
  - [What is Docker?](#what-is-docker)
  - [Without Docker vs With Docker](#without-docker-vs-with-docker)
  - [Configuration Decided](#configuration-decided)
  - [Scaffold Command](#scaffold-command)
- [Docker MCP Integration](#docker-mcp-integration)

## Docker

### What is Docker?

Docker is a tool that lets you run applications inside **containers** — think of them as small, self-contained boxes that include everything the app needs to run (code, dependencies, database, etc.). Instead of installing things directly on your computer, Docker packages it all together so it runs the same way everywhere.

Two key files make this work:

- **Dockerfile** — A recipe that describes how to build the container for your app (what base image, what to install, what command to run).
- **docker-compose.yml** — A file that describes how to run multiple containers together (e.g., Strapi + PostgreSQL) and how they connect to each other.

### Without Docker vs With Docker

Without Docker, you run Strapi directly on your machine. You need to manually install Node.js, PostgreSQL, and any native dependencies (like `sharp` for image processing). Every developer on the team has to do this setup themselves, and differences between machines (OS, versions, configs) can cause "works on my machine" bugs.

With Docker, you run `docker compose up` and everything starts automatically — Strapi, PostgreSQL, and all their dependencies — inside isolated containers.

|                             | Without Docker                                        | With Docker                                    |
| --------------------------- | ----------------------------------------------------- | ---------------------------------------------- |
| **Setup**                   | Install Node.js, PostgreSQL, and native deps manually | Run `docker compose up` — one command          |
| **Team onboarding**         | Each developer repeats the setup                      | Clone the repo, run one command, done          |
| **Environment differences** | Each machine may differ (OS, versions)                | Every machine runs the exact same containers   |
| **Database**                | Install and configure PostgreSQL yourself             | PostgreSQL starts automatically as a container |
| **Cleanup**                 | Uninstall everything manually                         | `docker compose down` removes everything       |

**Why we chose Docker:** Consistent environments, zero-effort setup for the team, and easier production deployments. Strapi does not provide official Docker images — you build your own.

### Configuration Decided

| Decision            | Choice                            | Why                                                                                                                |
| ------------------- | --------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| **Database**        | PostgreSQL (`postgres:16-alpine`) | Most common for Strapi, best community support. Used in both dev and prod for environment parity.                  |
| **Environments**    | Both (dev + prod)                 | Dev Dockerfile has hot-reload for local work. Prod Dockerfile uses a multi-stage build for lean, optimized images. |
| **Package manager** | pnpm                              | Matches the monorepo tooling. Strapi fully supports pnpm.                                                          |
| **File placement**  | `modules/cms/`                    | Keeps CMS Docker files alongside Strapi source, isolated from other modules.                                       |

**Why PostgreSQL over SQLite:**

- **Dev/prod parity** — Same database everywhere avoids surprises at deploy time (SQLite and PostgreSQL handle SQL differently).
- **Docker makes it zero-effort** — `docker compose up` spins up PostgreSQL automatically, so the convenience gap with SQLite disappears.
- **Team consistency** — Everyone gets the same database with one command.
- SQLite (a file-based embedded database) is fine for quick solo prototyping, but not for production or team workflows.

### Scaffold Command

The Strapi project was created from the repo root with:

```bash
pnpm create strapi modules/cms --skip-cloud --no-git-init --dbclient postgres --dbhost 127.0.0.1 --dbport 5432 --dbname strapi --dbusername strapi --dbpassword strapi --no-run --ts --no-example --install
```

| Flag                         | Why                                                                                    |
| ---------------------------- | -------------------------------------------------------------------------------------- |
| `--skip-cloud`               | We don't need Strapi Cloud login for local development.                                |
| `--no-git-init`              | The monorepo already has a git repo — no nested repo needed.                           |
| `--dbclient postgres`        | PostgreSQL as decided above. Requires all `--db*` params.                              |
| `--dbhost`, `--dbport`, etc. | Local defaults (`127.0.0.1:5432`, user/pass `strapi`). Overridden by `.env` in Docker. |
| `--no-run`                   | Don't auto-start after scaffolding — we set up Docker first.                           |
| `--ts`                       | TypeScript (default in Strapi 5, but explicit for clarity).                            |
| `--no-example`               | Clean start without example content types.                                             |
| `--install`                  | Install dependencies right away, skip the prompt.                                      |

## Docker MCP Integration

We added the Docker Hub MCP server to Claude Code so it can search Docker Hub and retrieve image metadata (tags, versions) in real time. This helps generate accurate `docker-compose.yaml` files without manual tag lookups.

**Setup:** Added via CLI with `claude mcp add MCP_DOCKER -s user -- docker mcp gateway run`. Requires Docker Desktop 4.48+.

**Note:** Public images work without credentials. For private repos, add a Docker Hub username and read-only personal access token in Docker Desktop → MCP Toolkit → Configuration.
