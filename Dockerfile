FROM python:3.15@sha256:407a8b2eb662a33acd1b0fc0363920e8446d8e647393177f137e0d5b6980565f AS builder

COPY --from=docker.io/astral/uv:0.13.8@sha256:5cc1805e2426484abca4ad46ea783bab281fdb225fd82d8ce6d66a81254bac85 /uv /usr/local/bin/uv

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

FROM python:3.15-slim@sha256:fd2aef5e0d8438208de9fe154ab5b331a2428fc0c9838d41611e611fd7a80d85

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
