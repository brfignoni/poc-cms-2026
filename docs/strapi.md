# Strapi - Decisions & Notes

<!-- Notes and decisions related to Strapi for this project. -->

## Docker

**Why we decided to use Docker for the project:**

- Ensures consistent environments across machines and team members.
- Simplifies dependency management (e.g., native deps like `sharp`/`libvips`).
- Makes production deployments to cloud/container platforms easier.

**Key considerations:**

- Strapi does not provide official Docker images — you build your own from the project.
- Use separate Dockerfiles for dev (hot-reload with `npm run develop`) and production (multi-stage builds).
- The admin panel URL (`STRAPI_ADMIN_BACKEND_URL`) is baked in at build time — must be set correctly or it defaults to `localhost:1337`.

**Quick start option:** `npx @strapi-community/dockerize@latest` generates a `Dockerfile` and `docker-compose.yml` tailored to the project.
