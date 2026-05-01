FROM python:3.12-slim

# Default to Swiss local time so uvicorn / app log timestamps match the
# operator's wall clock. Operators in other zones can override via the
# TZ env var in docker-compose without rebuilding. tzdata is bundled in
# the python:3.12-slim base, so /usr/share/zoneinfo/Europe/Zurich exists.
ENV TZ=Europe/Zurich

WORKDIR /app

# pyproject.toml is the single source of truth for runtime deps. Files
# referenced by [tool.setuptools] (server.py via py-modules, auth/ via
# packages) must be present for `pip install .` to succeed, so they are
# copied before the install. BuildKit cache mount keeps pip's wheel
# cache between builds — app-code changes that invalidate this layer do
# not re-download dependencies.
COPY pyproject.toml server.py ./
COPY auth/ auth/
RUN --mount=type=cache,target=/root/.cache/pip pip install .

# Static frontend assets, separated so PWA-only edits don't invalidate
# the install above.
COPY pwa/ pwa/

# The integration reference (endpoint map + backend contract) is served
# live at /integration so integrators can curl it without checking out
# the repo.
COPY docs/integration.md ./integration.md

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
