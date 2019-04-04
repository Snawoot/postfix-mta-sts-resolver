## Configuration

Configuration file is a YAML document.

Reference for configuration values:

* `host`: (str) daemon bind address
* `port`: (int) daemon bind port
* `reuse_port`: (bool) allow multiple instances to share same port (available on Unix, Windows)
* `cache_grace`: (float) age of cache entries in seconds which do not require policy refresh and update. Default: 60
* `cache`:
  * `type`: (str: `internal`|`sqlite`|`redis`) cache backend type
  * `options`:
    * Options for `internal` type:
      * `cache_size`: (int) number of cache entries to store in memory
    * Options for `sqlite` type:
      * `filename`: (str) path to database file
      * `threads`: (int) number of threads in pool for SQLite connections
      * `timeout`: (float) timeout in seconds for acquiring connection from pool or DB lock
    * Options for `redis` type:
      * All parameters are passed to [aioredis.create_redis_pool](https://aioredis.readthedocs.io/en/latest/api_reference.html#aioredis.create_redis_pool). Use it for parameter reference.
* `default_zone`:
  * `strict_testing`: (bool) enforce policy for testing domains
  * `timeout`: (int) network operations timeout for resolver in that zone
* `zones`:
  * `ZONENAME`:
    * Same as options in default zone
