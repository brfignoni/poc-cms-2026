# Strapi - Decisions & Notes

<!-- Notes and decisions related to Strapi for this project. -->

## Index

- [Docker](#docker)
  - [What is Docker?](#what-is-docker)
  - [Without Docker vs With Docker](#without-docker-vs-with-docker)
  - [How Docker Connects with Strapi](#how-docker-connects-with-strapi)
  - [Configuration Decided](#configuration-decided)
  - [Scaffold Command](#scaffold-command)
  - [Docker Files Reference](#docker-files-reference)
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

### How Docker Connects with Strapi

When you run `docker compose up`, Docker creates two containers and a private network so they can talk to each other:

```
┌──────────────────────────────────────────────────────┐
│                Docker Network "strapi"                │
│                                                      │
│  ┌────────────────┐         ┌────────────────┐       │
│  │    strapi       │         │   strapiDB     │       │
│  │   (Node.js)     │────────▶│  (PostgreSQL)  │       │
│  │   port 1337     │         │   port 5432    │       │
│  └────────────────┘         └────────────────┘       │
│                                                      │
└──────────────────────────────────────────────────────┘
          │
          ▼
    localhost:1337 (your browser)
```

**How it works step by step:**

1. Docker creates a private network called `strapi`.
2. Docker starts the PostgreSQL container and names it `strapiDB`.
3. Docker waits for PostgreSQL's healthcheck to pass (is the DB ready?).
4. Docker starts the Strapi container and injects all variables from `.env`.
5. Strapi reads `DATABASE_HOST=strapiDB` and connects to PostgreSQL **by container name** — inside Docker's network, container names work like hostnames.
6. You open `http://localhost:1337/admin` in your browser.

The key is the `.env` variable `DATABASE_HOST=strapiDB`. Inside Docker, containers find each other by name, not by IP address. That's why we use `strapiDB` (the container name) instead of `127.0.0.1` (your Mac).

**Monorepo note:** The build context is set to `../..` (the repo root) because pnpm keeps a single `pnpm-lock.yaml` at the root. Docker needs access to it. The `--filter cms` flag tells pnpm to install only the CMS module's dependencies.

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

### Docker Files Reference

All Docker files live in `modules/cms/`:

| File                      | What it does                                                                           |
| ------------------------- | -------------------------------------------------------------------------------------- |
| `.dockerignore`           | Tells Docker what NOT to copy into the image (`node_modules`, `.env`, etc.)            |
| `Dockerfile`              | Dev image — installs deps, runs `pnpm run develop` with hot-reload                     |
| `Dockerfile.prod`         | Prod image — two-stage build: first builds everything, second keeps only what's needed |
| `docker-compose.yml`      | Dev orchestrator — starts Strapi + PostgreSQL with volume mounts for live editing      |
| `docker-compose.prod.yml` | Prod orchestrator — same but optimized (no volume mounts, port only on localhost)      |
| `.env.example`            | Template with all required environment variables                                       |

**Usage from `modules/cms/`:**

```bash
# Development (hot-reload)
docker compose up --build

# Production
docker compose -f docker-compose.prod.yml up --build

# Stop and remove containers
docker compose down

# Stop and also delete the database data
docker compose down -v
```

## Docker MCP Integration

> **Note:** This was only needed during the initial setup. Now that the Docker files are in place, this MCP server is no longer relevant for day-to-day work.

We connected Claude Code to Docker Hub via MCP so it could look up the correct image names and tags (`node:22-alpine`, `postgres:16-alpine`) when generating the Docker configuration.
