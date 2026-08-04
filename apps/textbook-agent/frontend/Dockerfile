FROM node:20-slim AS builder

WORKDIR /app/frontend

COPY --from=lectio / /lectio/

COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./

ARG PUBLIC_API_URL=http://localhost:8000
ARG VITE_GOOGLE_CLIENT_ID=
ENV PUBLIC_API_URL=$PUBLIC_API_URL
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID

RUN npm ci

COPY frontend/ ./

RUN npm run build

FROM nginx:1.27-alpine AS runtime

COPY --from=builder /app/frontend/build /usr/share/nginx/html

RUN printf '%s\n' \
    'server {' \
    '  listen 80;' \
    '  server_name _;' \
    '  root /usr/share/nginx/html;' \
    '  index index.html;' \
    '  location / {' \
    '    try_files $uri $uri/ /index.html;' \
    '  }' \
    '}' \
    > /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
