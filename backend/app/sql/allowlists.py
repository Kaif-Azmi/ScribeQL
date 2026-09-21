"""
Per-dialect function blocklists and system namespace blocklists for ScribeQL SQL safety.

Design notes
------------
- Function names must match the SQL-level name, lowercased (e.g. "pg_sleep" not "PgSleep").
- For sqlglot-recognised functions, this is what .sql_name() returns lowercased.
- For anonymous (unrecognised) functions, this is what the parser sees in the text.
- BLOCKED_ROOT_NODE_TYPES uses Python class names from sqlglot.expressions.*
  since that is what type(node).__name__ returns during AST walking.
"""

# ---------------------------------------------------------------------------
# Blocked functions — PostgreSQL
# ---------------------------------------------------------------------------
BLOCKED_FUNCTIONS_POSTGRES: frozenset[str] = frozenset({
    # Timing / denial-of-service
    "pg_sleep",
    "pg_sleep_for",
    "pg_sleep_until",

    # File-system access
    "pg_read_file",
    "pg_read_binary_file",
    "pg_ls_dir",
    "pg_ls_logdir",
    "pg_ls_waldir",
    "pg_ls_tmpdir",
    "pg_stat_file",

    # Large-object (LOB) I/O — writes / reads arbitrary server files
    "lo_import",
    "lo_export",
    "lo_create",
    "lo_unlink",
    "lo_open",
    "lo_read",
    "lo_write",
    "lo_close",
    "lo_get",
    "lo_put",
    "lo_truncate",
    "lo_lseek",
    "lo_tell",

    # Server config and session state manipulation
    "current_setting",   # can leak secrets (e.g. LLM keys via GUCs)
    "set_config",
    "pg_reload_conf",

    # Process / backend control
    "pg_cancel_backend",
    "pg_terminate_backend",
    "pg_rotate_logfile",
    "pg_switch_wal",
    "pg_checkpoint",

    # Advisory locks (allow inter-session coordination / DoS)
    "pg_advisory_lock",
    "pg_advisory_lock_shared",
    "pg_advisory_unlock",
    "pg_advisory_unlock_shared",
    "pg_advisory_unlock_all",
    "pg_advisory_xact_lock",
    "pg_advisory_xact_lock_shared",
    "pg_try_advisory_lock",
    "pg_try_advisory_lock_shared",
    "pg_try_advisory_xact_lock",
    "pg_try_advisory_xact_lock_shared",

    # Foreign data wrappers / remote SQL execution
    "dblink",
    "dblink_exec",
    "dblink_connect",
    "dblink_connect_u",
    "dblink_disconnect",
    "dblink_open",
    "dblink_fetch",
    "dblink_close",
    "postgres_fdw_handler",

    # COPY helpers (server-side file access)
    "copy_to",
    "copy_from",

    # Sequence mutation (write side-effect inside a SELECT)
    "setval",

    # Server-state probes that can reveal internal structure
    "pg_trigger_depth",
    "pg_backend_pid",       # can be combined with pg_cancel_backend
    "pg_postmaster_start_time",
})


# ---------------------------------------------------------------------------
# Blocked functions — MySQL
# ---------------------------------------------------------------------------
BLOCKED_FUNCTIONS_MYSQL: frozenset[str] = frozenset({
    # File access
    "load_file",

    # Timing / denial-of-service
    "sleep",
    "benchmark",

    # Locking
    "get_lock",
    "release_lock",
    "release_all_locks",
    "is_free_lock",
    "is_used_lock",

    # External execution (available in some MySQL forks / UDF environments)
    "sys_exec",
    "sys_eval",
})


# ---------------------------------------------------------------------------
# System / application namespaces — PostgreSQL
# Accessing any of these reveals internal state or ScribeQL app data.
# ---------------------------------------------------------------------------
SYSTEM_NAMESPACES_POSTGRES: frozenset[str] = frozenset({
    "pg_catalog",
    "information_schema",
    "pg_toast",
    "pg_temp",
    "pg_toast_temp",
    # ScribeQL's own application schema — must never be exposed to generated SQL
    "app",
})


# ---------------------------------------------------------------------------
# System / application namespaces — MySQL
# ---------------------------------------------------------------------------
SYSTEM_NAMESPACES_MYSQL: frozenset[str] = frozenset({
    "mysql",
    "information_schema",
    "performance_schema",
    "sys",
    # ScribeQL application schema
    "app",
})


# ---------------------------------------------------------------------------
# Statement node-type names that must never appear anywhere in the AST.
# These are Python class names from sqlglot.expressions (type(node).__name__).
# The root-level check (step 3) catches most of these; this set provides
# defence-in-depth by catching the same types when nested inside a WITH or
# subquery (e.g. writable CTEs: WITH x AS (DELETE ... RETURNING) SELECT ...).
# ---------------------------------------------------------------------------
BLOCKED_ROOT_NODE_TYPES: frozenset[str] = frozenset({
    # DML writes
    "Insert",
    "Update",
    "Delete",
    "Merge",

    # DDL
    "Create",
    "Drop",
    "Alter",
    "Truncate",
    "Rename",

    # Control / admin
    "Command",      # sqlglot's catch-all for unrecognised statements
    "Use",
    "Copy",         # PostgreSQL COPY TO/FROM
    "Show",
    "Describe",
    "Explain",
    "Set",
    "Transaction",
    "Commit",
    "Rollback",
    "Savepoint",
    "ReleaseSavepoint",
    "Call",
    "Execute",
    "Declare",
    "Grant",
    "Revoke",
    "Replace",      # MySQL REPLACE INTO (write)
})
