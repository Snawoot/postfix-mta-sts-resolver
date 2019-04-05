from multiprocessing import cpu_count

HOST = "127.0.0.1"
PORT = 8461
REUSE_PORT = True
TIMEOUT = 4
SHUTDOWN_TIMEOUT = 20
STRICT_TESTING = False
CONFIG_LOCATION = "/etc/postfix/mta-sts-daemon.yml"
CACHE_BACKEND = "internal"
INTERNAL_CACHE_SIZE = 10000
SQLITE_THREADS = cpu_count()
SQLITE_TIMEOUT = 5
REDIS_TIMEOUT = 5
CACHE_GRACE = 60
