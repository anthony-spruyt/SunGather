FROM python:3.14@sha256:779838536f5a0d42d150edbf59fcb08af24fd21b3dd6af7f308dbadcbb6ff3cc AS builder

WORKDIR /build

# hadolint ignore=DL3008
RUN python3 -m venv /opt/virtualenv \
 && apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY SunGather/requirements.txt ./
RUN /opt/virtualenv/bin/pip3 install --no-cache-dir -r requirements.txt

# Test stage: includes pytest and source code for CI
FROM builder AS test

WORKDIR /opt/sungather
COPY SunGather/ ./SunGather/
COPY pyproject.toml ./
RUN /opt/virtualenv/bin/pip3 install --no-cache-dir pytest

# Production stage
FROM python:3.14-slim@sha256:7bf6c3111fe094f8ee1a1cbcdc63c4cfb345b0e3df42d5aa9a90b3b4b022ab6d

# hadolint ignore=DL3027,DL3008
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && rm -rf /var/lib/apt/lists/* \
 && useradd -r -m -u 999 sungather

COPY --from=builder /opt/virtualenv /opt/virtualenv

WORKDIR /opt/sungather

COPY SunGather/ .

VOLUME /logs
VOLUME /config
COPY SunGather/config-example.yaml /config/config.yaml

USER 999

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD [ "/opt/virtualenv/bin/python", "-c", \
        "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" ]

CMD [ "/opt/virtualenv/bin/python", "sungather.py", "-c", "/config/config.yaml", "-l", "/logs/" ]
