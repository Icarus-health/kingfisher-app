# Kingfisher: statische React-Oberfläche plus lokaler FastAPI-/SQLite-Prozess.

FROM node:22-alpine AS ui-build
WORKDIR /workspace
COPY app/kingfisher/package.json app/kingfisher/package-lock.json app/kingfisher/
RUN cd app/kingfisher && npm ci
COPY app/kingfisher app/kingfisher
COPY design-source design-source
RUN cd app/kingfisher && npm run build

FROM python:3.12-slim AS python-build
WORKDIR /build
COPY sidecar/pyproject.toml sidecar/pyproject.toml
COPY sidecar/icarus_memory sidecar/icarus_memory
RUN pip install --no-cache-dir --prefix=/install "./sidecar"

FROM python:3.12-slim AS runtime
# Die Fassung dieses Bildes (docs/53-download-und-updates.md). Der Release-Workflow setzt sie aus `VERSION`; ein lokal
# gebautes Bild liest dieselbe Datei unter /opt/kingfisher/VERSION.
ARG KINGFISHER_FASSUNG=""
ENV KINGFISHER_FASSUNG=${KINGFISHER_FASSUNG}
RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin kingfisher
COPY --from=python-build /install /usr/local
COPY --from=ui-build /workspace/app/dist /opt/kingfisher/ui
COPY VERSION /opt/kingfisher/VERSION

ENV ICARUS_DATA_DIR=/data
ENV ICARUS_FILE_ROOTS=""
ENV ICARUS_SIDECAR_HOST=0.0.0.0
ENV ICARUS_SIDECAR_PORT=8890
ENV ICARUS_UI_DIR=/opt/kingfisher/ui
RUN mkdir -p /data && chown kingfisher:kingfisher /data
VOLUME ["/data"]

WORKDIR /home/kingfisher
USER kingfisher
EXPOSE 8890
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8890/health', timeout=2)" || exit 1
ENTRYPOINT ["icarus-sidecar"]
