FROM docker.io/python:3.7-alpine
LABEL maintainer="Vladislav Yarmak <vladislav-ex-src@vm-0.com>"

COPY . /build
WORKDIR /build
RUN true \
   && apk add --no-cache --virtual .build-deps alpine-sdk libffi-dev \
   && apk add --no-cache libffi \
   && pip3 install --no-cache-dir .[sqlite,redis] \
   && pip3 install --no-cache-dir uvloop \
   && apk del .build-deps \
   && true
COPY docker-config.yml /etc/mta-sts-daemon.yml

VOLUME [ "/var/lib/mta-sts" ]
EXPOSE 8461/tcp
ENTRYPOINT [ "mta-sts-daemon" ]
