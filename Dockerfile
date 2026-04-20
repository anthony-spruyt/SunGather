FROM python:3.14@sha256:ffebef43892dd36262fa2b042eddd3320d5510a21f8440dce0a650a3c124b51d AS builder

WORKDIR /build

# hadolint ignore=DL3008
RUN python3 -m venv /opt/virtualenv \
 && apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN /opt/virtualenv/bin/pip3 install --no-cache-dir -r requirements.txt

# Test stage: includes pytest and source code for CI
FROM builder AS test

WORKDIR /opt/sungather
COPY SunGather/ ./SunGather/
COPY pyproject.toml ./
RUN /opt/virtualenv/bin/pip3 install --no-cache-dir pytest

# Production stage
FROM python:3.14-slim@sha256:bc389f7dfcb21413e72a28f491985326994795e34d2b86c8ae2f417b4e7818aa

RUN useradd -r -m sungather

COPY --from=builder /opt/virtualenv /opt/virtualenv

WORKDIR /opt/sungather

COPY SunGather/ .

VOLUME /logs
VOLUME /config
COPY SunGather/config-example.yaml /config/config.yaml

USER sungather

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD /opt/virtualenv/bin/python -c \
  "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" \
  || exit 1

CMD [ "/opt/virtualenv/bin/python", "sungather.py", "-c", "/config/config.yaml", "-l", "/logs/" ]
