FROM python:3.14@sha256:b3ae2372f3c9b7f0a80ec21d1ae931002ea056509e04c5072f144efe9694732f AS builder

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

FROM python:3.14-slim@sha256:0214bda9af2652a418f2bf34373a4d3ca00a5f4784081e040049433ac9cc79d5

# hadolint ignore=DL3027,DL3008
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && rm -rf /var/lib/apt/lists/* \
 && useradd -r -m -u 999 sungather

# Nothing installs packages at runtime, so pip stays out of the image.
RUN python -m pip uninstall --yes --root-user-action=ignore pip \
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
