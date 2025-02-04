from multiprocessing import cpu_count

HOST = "127.0.0.1"
PORT = 8461
REUSE_PORT = True
TIMEOUT = 4
TLSRPT = False
SHUTDOWN_TIMEOUT = 20
STRICT_TESTING = False
CONFIG_LOCATION = "/etc/mta-sts-daemon.yml"
CACHE_BACKEND = "internal"
INTERNAL_CACHE_SIZE = 10000
SQLITE_THREADS = cpu_count()
SQLITE_TIMEOUT = 5
POSTGRES_TIMEOUT = 5
REDIS_CONNECT_TIMEOUT = 5
REDIS_TIMEOUT = 5
CACHE_GRACE = 60
PROACTIVE_FETCH_ENABLED = False
PROACTIVE_FETCH_INTERVAL = 86400
PROACTIVE_FETCH_CONCURRENCY_LIMIT = 100
PROACTIVE_FETCH_GRACE_RATIO = 2.0
USER_AGENT = "postfix-mta-sts-resolver"
REQUIRE_SNI = True
