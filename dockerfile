FROM docker:29-cli AS docker-cli

FROM python:3.14-slim

ARG APP_VERSION=dev
ARG APP_GIT_SHA=unknown
ARG APP_BUILD_DATE=unknown
ARG APP_BUILD_RUN=local

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV ADMINNGINX_VERSION=${APP_VERSION}
ENV ADMINNGINX_GIT_SHA=${APP_GIT_SHA}
ENV ADMINNGINX_BUILD_DATE=${APP_BUILD_DATE}
ENV ADMINNGINX_BUILD_RUN=${APP_BUILD_RUN}

LABEL org.opencontainers.image.title="adminnginx"
LABEL org.opencontainers.image.version="${APP_VERSION}"
LABEL org.opencontainers.image.revision="${APP_GIT_SHA}"
LABEL org.opencontainers.image.created="${APP_BUILD_DATE}"
LABEL org.opencontainers.image.source="https://github.com/seah78/adminnginx"

WORKDIR /app

COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker-cli /usr/local/libexec/docker/cli-plugins \
    /usr/local/libexec/docker/cli-plugins

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        netcat-openbsd \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . /app/

RUN sed -i 's/\r$//' /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
