# The platform's tooling image: the dashboard and API, the canary analysis Jenkins runs, and the rule generator.
FROM node:22-slim AS web
WORKDIR /web
RUN corepack enable
COPY web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SEP_WEB_DIST=/app/web/dist
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY sep ./sep
COPY config ./config
COPY reports ./reports
COPY edge ./edge
COPY --from=web /web/dist ./web/dist
RUN useradd --create-home app && chown -R app /app
USER app
EXPOSE 8080
CMD ["uvicorn", "sep.service.api:app", "--host", "0.0.0.0", "--port", "8080"]
