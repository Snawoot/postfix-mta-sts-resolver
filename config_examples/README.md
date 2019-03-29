## Configuration

Configuration file is a YAML document.

Reference for configuration values:

* `host`: (str) daemon bind address
* `port`: (int) daemon bind port
* `reuse_port`: (bool) allow multiple instances to share same port (available on Unix, Windows)
* `cache`:
  * `type`: (str: `internal`|`sqlite`) cache backend type
  * `options`:
    * Options for `internal` type:
      * `cache_size`: (int) number of cache entries to store in memory
    * Options for `sqlite` type:
      * `filename`: (str) path to database file
* `default_zone`:
  * `strict_testing`: (bool) enforce policy for testing domains
  * `timeout`: (int) network operations timeout for resolver in that zone
* `zones`:
  * `ZONENAME`:
    * Same as options in default zone
