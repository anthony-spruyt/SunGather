FROM python:3.14@sha256:f6dbe23bffcae1ffd9833dab20d62791295510df0269a43c5456bd8f0d064d25 AS builder

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
FROM python:3.14-slim@sha256:b921fe7e7522f828d45197a47656ec465a9b15689b27fa8e1fba2864fca5b967

# hadolint ignore=DL3027,DL3008
RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/*

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
