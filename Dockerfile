FROM python:3-slim
LABEL maintainer="Vladislav Yarmak <vladislav-ex-src@vm-0.com>"

COPY . /build
WORKDIR /build
RUN pip3 install --no-cache-dir .[sqlite,redis] && pip3 install --no-cache-dir uvloop
COPY docker-config.yml /etc/mta-sts-daemon.yml

VOLUME [ "/var/lib/mta-sts" ]
EXPOSE 8461/tcp
ENTRYPOINT [ "mta-sts-daemon" ]
