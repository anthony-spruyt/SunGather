FROM python:3.15@sha256:4df75c7aaf4687361abf29acab2b97fef332cbc9a0d1ca10e69e82d13ba5b00f AS builder

COPY --from=docker.io/astral/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff /uv /usr/local/bin/uv

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

FROM python:3.15-slim@sha256:7ce16513bf93a92cb89160580a412fa2735707ce2a312257b7a1fd8242cd11c6

# Nothing installs packages at runtime, so pip stays out of the image.
# hadolint ignore=DL3027,DL3008
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && rm -rf /var/lib/apt/lists/* \
 && useradd -r -m -u 999 sungather \
 && python -m pip uninstall --yes --root-user-action=ignore pip \
 && rm -f /usr/local/bin/pip

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
