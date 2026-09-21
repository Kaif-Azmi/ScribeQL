from typing import Tuple, Dict, Any
from unittest.mock import patch
import io
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.auth.service import auth_service, in_memory_auth_store
from app.sessions.service import query_session_service, in_memory_query_store
from app.schema.storage import in_memory_schema_store

client = TestClient(app)
ORIGIN_HEADER = {"Origin": "http://localhost:5173"}


def setup_function():
    in_memory_auth_store.clear()
    in_memory_query_store.clear()
    in_memory_schema_store.clear()


def create_authenticated_user_and_custom_session(email: str = "upload@example.com") -> Tuple[str, str, str]:
    _, v_token = auth_service.signup(email, "password123456")
    user_dict, auth_cookie = auth_service.verify_email(v_token)
    sess = query_session_service.create_session(user_dict["id"], "custom")
    return user_dict["id"], auth_cookie, sess["session_id"]


def test_valid_postgres_ddl_upload():
    with patch("app.auth.service.check_db_health", return_value=False), \
         patch("app.sessions.service.check_db_health", return_value=False), \
         patch("app.schema.storage.check_db_health", return_value=False):

        _, auth_cookie, session_id = create_authenticated_user_and_custom_session()

        pg_ddl = """
        CREATE TABLE categories (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL
        );
        CREATE TABLE products (
            id SERIAL PRIMARY KEY,
            category_id INT NOT NULL REFERENCES categories(id),
            title VARCHAR(200) NOT NULL,
            price NUMERIC(10,2) NOT NULL
        );
        CREATE INDEX idx_products_cat ON products(category_id);
        """

        resp = client.post(
            "/api/schema/upload",
            data={"session_id": session_id, "dialect": "postgres"},
            files={"file": ("schema.sql", io.BytesIO(pg_ddl.encode("utf-8")), "text/plain")},
            cookies={"__Host-sid": auth_cookie},
            headers=ORIGIN_HEADER
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["dialect"] == "postgres"
        assert len(data["tables"]) == 2
        assert data["fk_count"] == 1
        assert "schema_id" in data
        assert any("Skipped unsupported statements" in w for w in data["warnings"])


def test_valid_mysql_ddl_upload():
    with patch("app.auth.service.check_db_health", return_value=False), \
         patch("app.sessions.service.check_db_health", return_value=False), \
         patch("app.schema.storage.check_db_health", return_value=False):

        _, auth_cookie, session_id = create_authenticated_user_and_custom_session("mysql@example.com")

        mysql_ddl = """
        CREATE TABLE `users` (
            `id` int NOT NULL AUTO_INCREMENT,
            `username` varchar(50) NOT NULL,
            PRIMARY KEY (`id`)
        ) ENGINE=InnoDB;
        """

        resp = client.post(
            "/api/schema/upload",
            data={"session_id": session_id, "dialect": "mysql"},
            files={"file": ("schema.sql", io.BytesIO(mysql_ddl.encode("utf-8")), "text/plain")},
            cookies={"__Host-sid": auth_cookie},
            headers=ORIGIN_HEADER
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["dialect"] == "mysql"
        assert data["tables"][0]["name"] == "users"


def test_invalid_ddl_returns_400_ddl_parse_error():
    with patch("app.auth.service.check_db_health", return_value=False), \
         patch("app.sessions.service.check_db_health", return_value=False), \
         patch("app.schema.storage.check_db_health", return_value=False):

        _, auth_cookie, session_id = create_authenticated_user_and_custom_session("invalid@example.com")

        invalid_ddl = "SELECT * FROM non_existent_table;"

        resp = client.post(
            "/api/schema/upload",
            data={"session_id": session_id, "dialect": "postgres"},
            files={"file": ("schema.sql", io.BytesIO(invalid_ddl.encode("utf-8")), "text/plain")},
            cookies={"__Host-sid": auth_cookie},
            headers=ORIGIN_HEADER
        )

        assert resp.status_code == 400
        assert resp.json()["error"]["type"] == "ddl_parse_error"


def test_reserved_namespace_returns_400():
    with patch("app.auth.service.check_db_health", return_value=False), \
         patch("app.sessions.service.check_db_health", return_value=False), \
         patch("app.schema.storage.check_db_health", return_value=False):

        _, auth_cookie, session_id = create_authenticated_user_and_custom_session("sys@example.com")

        sys_ddl = "CREATE TABLE sys.audit_log (id INT PRIMARY KEY);"

        resp = client.post(
            "/api/schema/upload",
            data={"session_id": session_id, "dialect": "postgres"},
            files={"file": ("schema.sql", io.BytesIO(sys_ddl.encode("utf-8")), "text/plain")},
            cookies={"__Host-sid": auth_cookie},
            headers=ORIGIN_HEADER
        )

        assert resp.status_code == 400
        assert resp.json()["error"]["type"] == "reserved_namespace"


def test_file_size_cap_returns_413():
    with patch("app.auth.service.check_db_health", return_value=False), \
         patch("app.sessions.service.check_db_health", return_value=False), \
         patch("app.schema.storage.check_db_health", return_value=False):

        _, auth_cookie, session_id = create_authenticated_user_and_custom_session("large@example.com")

        # Over 200 KB
        large_bytes = b"A" * (205 * 1024)

        resp = client.post(
            "/api/schema/upload",
            data={"session_id": session_id, "dialect": "postgres"},
            files={"file": ("big.sql", io.BytesIO(large_bytes), "text/plain")},
            cookies={"__Host-sid": auth_cookie},
            headers=ORIGIN_HEADER
        )

        assert resp.status_code == 413
        assert resp.json()["error"]["type"] == "file_too_large"


def test_demo_session_returns_409_wrong_session_mode():
    with patch("app.auth.service.check_db_health", return_value=False), \
         patch("app.sessions.service.check_db_health", return_value=False), \
         patch("app.schema.storage.check_db_health", return_value=False):

        u_dict, auth_cookie = auth_service.verify_email(auth_service.signup("demo_user@example.com", "password123456")[1])
        demo_sess = query_session_service.create_session(u_dict["id"], "demo")

        pg_ddl = "CREATE TABLE dummy (id INT PRIMARY KEY);"

        resp = client.post(
            "/api/schema/upload",
            data={"session_id": demo_sess["session_id"], "dialect": "postgres"},
            files={"file": ("schema.sql", io.BytesIO(pg_ddl.encode("utf-8")), "text/plain")},
            cookies={"__Host-sid": auth_cookie},
            headers=ORIGIN_HEADER
        )

        assert resp.status_code == 409
        assert resp.json()["error"]["type"] == "wrong_session_mode"


def test_dialect_locked_returns_409():
    with patch("app.auth.service.check_db_health", return_value=False), \
         patch("app.sessions.service.check_db_health", return_value=False), \
         patch("app.schema.storage.check_db_health", return_value=False):

        _, auth_cookie, session_id = create_authenticated_user_and_custom_session("locked@example.com")

        ddl = "CREATE TABLE items (id INT PRIMARY KEY);"

        # 1. Upload in postgres -> sets dialect to postgres
        resp1 = client.post(
            "/api/schema/upload",
            data={"session_id": session_id, "dialect": "postgres"},
            files={"file": ("schema.sql", io.BytesIO(ddl.encode("utf-8")), "text/plain")},
            cookies={"__Host-sid": auth_cookie},
            headers=ORIGIN_HEADER
        )
        assert resp1.status_code == 200

        # 2. Upload same session in mysql -> 409 dialect_locked
        resp2 = client.post(
            "/api/schema/upload",
            data={"session_id": session_id, "dialect": "mysql"},
            files={"file": ("schema.sql", io.BytesIO(ddl.encode("utf-8")), "text/plain")},
            cookies={"__Host-sid": auth_cookie},
            headers=ORIGIN_HEADER
        )
        assert resp2.status_code == 409
        assert resp2.json()["error"]["type"] == "dialect_locked"
