FROM python:3.14@sha256:779838536f5a0d42d150edbf59fcb08af24fd21b3dd6af7f308dbadcbb6ff3cc AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.23@sha256:61d393e44e249f2e4b526b6c7ddcecce245946826e608e11c93ad4f5bba55b21 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/virtualenv \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /build

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-build --no-dev --no-install-project

COPY README.md LICENSE ./
COPY src/ ./src/
RUN uv sync --frozen --no-build --no-dev --no-editable

FROM python:3.14-slim@sha256:65a94bb37b630c482dfd31e5fb9b449cb26c31eab1b7a125cd6bd624acfe3b30

# hadolint ignore=DL3027,DL3008
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && rm -rf /var/lib/apt/lists/* \
 && useradd -r -m -u 999 sungather

COPY --from=builder /opt/virtualenv /opt/virtualenv

WORKDIR /opt/sungather

VOLUME /logs
VOLUME /config
COPY src/sungather/config-example.yaml /config/config.yaml

USER 999

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD [ "/opt/virtualenv/bin/python", "-c", \
        "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" ]

CMD [ "/opt/virtualenv/bin/sungather", "-c", "/config/config.yaml", "-l", "/logs/" ]
