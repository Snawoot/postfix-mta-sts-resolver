FROM docker.io/python:3.8-alpine
LABEL maintainer="Vladislav Yarmak <vladislav-ex-src@vm-0.com>"

ARG UID=18721
ARG USER=mta-sts
ARG GID=18721

RUN true \
   && addgroup --gid "$GID" "$USER" \
   && adduser \
        --disabled-password \
        --gecos "" \
        --home "/build" \
        --ingroup "$USER" \
        --no-create-home \
        --uid "$UID" \
        "$USER" \
   && true

COPY . /build
WORKDIR /build
RUN true \
   && apk add --no-cache --virtual .build-deps alpine-sdk libffi-dev \
   && apk add --no-cache libffi \
   && pip3 install --no-cache-dir .[sqlite,redis,uvloop] \
   && mkdir /var/lib/mta-sts \
   && chown -R "$USER:$USER" /build /var/lib/mta-sts \
   && apk del .build-deps \
   && true
COPY docker-config.yml /etc/mta-sts-daemon.yml

USER $USER

VOLUME [ "/var/lib/mta-sts" ]
EXPOSE 8461/tcp
ENTRYPOINT [ "mta-sts-daemon" ]
