# ---------- Build stage ----------
FROM node:lts-alpine AS build

WORKDIR /app

# 👇 IMPORTANT: pin pnpm version to match local
RUN corepack enable \
 && corepack prepare pnpm@9.15.4 --activate

COPY package.json pnpm-lock.yaml ./

# Frozen lockfile now works
RUN pnpm install --frozen-lockfile

COPY . .

ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}
RUN ./node_modules/.bin/vite build

# ---------- Production stage ----------
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
