FROM python:3.15@sha256:c6ecb2f3c3dc85a75350f36560e1f49d35d6a9f7ce11fd775bd6834a69a9a0e1 AS builder

COPY --from=docker.io/astral/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 /uv /usr/local/bin/uv

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

FROM python:3.14-slim@sha256:4b20ddacd9adac0002725db940785e17c19d0c3ed1843f31e57418988effc58c

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
