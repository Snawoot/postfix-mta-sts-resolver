FROM python:3-slim
LABEL maintainer="Vladislav Yarmak <vladislav-ex-src@vm-0.com>"

COPY docker-config.yml /etc/mta-sts-daemon.yml
RUN pip3 install --no-cache-dir postfix-mta-sts-resolver uvloop

VOLUME [ "/var/lib/mta-sts" ]
EXPOSE 8461/tcp
ENTRYPOINT [ "mta-sts-daemon", "-c", "/etc/mta-sts-daemon.yml" ]
