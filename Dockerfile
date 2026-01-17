FROM python:3.13 AS builder

RUN python3 -m venv /opt/virtualenv \
 && apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN /opt/virtualenv/bin/pip3 install --no-cache-dir -r requirements.txt

FROM python:3.13-slim

RUN useradd -r -m sungather

COPY --from=builder /opt/virtualenv /opt/virtualenv

WORKDIR /opt/sungather

COPY SunGather/ .

VOLUME /logs
VOLUME /config
COPY SunGather/config-example.yaml /config/config.yaml

USER sungather

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
  CMD /opt/virtualenv/bin/python -c "print('ok')" || exit 1

CMD [ "/opt/virtualenv/bin/python", "sungather.py", "-c", "/config/config.yaml", "-l", "/logs/" ]
