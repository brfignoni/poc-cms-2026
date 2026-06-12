# Development Dockerfile for Strapi CMS
# Build context must be the monorepo root (set in docker-compose.yml)
FROM node:22-alpine

# Install native build deps for sharp/libvips
RUN apk update && apk add --no-cache build-base gcc autoconf automake zlib-dev libpng-dev bash vips-dev git

# Enable pnpm via corepack
RUN corepack enable && corepack prepare pnpm@9.15.9 --activate

ARG NODE_ENV=development
ENV NODE_ENV=${NODE_ENV}

# Install dependencies using pnpm workspace filter
WORKDIR /opt/
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY modules/cms/package.json ./modules/cms/
RUN pnpm install --frozen-lockfile --filter cms

# Copy CMS source code
WORKDIR /opt/modules/cms
COPY modules/cms/ .

RUN chown -R node:node /opt
USER node
EXPOSE 1337
CMD ["pnpm", "run", "develop"]
