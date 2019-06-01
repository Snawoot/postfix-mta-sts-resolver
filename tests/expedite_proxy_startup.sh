#!/bin/sh

for p in 5 60 60 ; do
    curl -s -o /dev/null \
        -x http://127.0.0.2:1380 \
        https://mta-sts.good.loc/.well-known/mta-sts.txt && exit 0
    >&2 printf "Proxy startup failed. Restarting in %d seconds..." "$p"
    sleep "$p"
    systemctl stop tinyproxy
    sleep 1
    killall -9 tinyproxy
    systemctl start tinyproxy
done

exit 1
