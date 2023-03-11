# Deployment

## RHEL/CentOS/OEL

The default Python version in RHEL7 (and clones) is too old, you need at least 3.5 to run postfix-mta-sts. However, Python 3.6 is available in the Software collections

For other distributions please edit the Systemd Unit file accordingly

### Create a User (and Group) to run MTA-STS
```bash
useradd -c "Daemon for MTA-STS policy checks" mta-sts -s /sbin/nologin
```

### Systemd Unit file

Place the provided files to /etc/systemd/system and reload the system daemon

```bash
systemctl daemon-reload
```

To enable MTA-STS on system startup run

```bash
systemctl enable postfix-mta-sts.service
```

## FreeBSD rc.d file

Place the provided mta-sts-daemon file to /usr/local/etc/rc.d

To enable MTA-STS on system startup add `mta_sts_daemon_enable="YES"` to your /etc/rc.conf

## NetBSD rc.d file

Place the provided `mta_sts_daemon.netbsd` file to `/etc/rc.d/`.

You want to verify that `command_interpreter` is set to your correct python interpreter.

Also make sure that you have added the `mta-sts` user and group.

To enable MTA-STS on system startup add `mta_sts_daemon="YES"` to your `/etc/rc.conf`.

