from unittest.mock import MagicMock
import pytest
from app.schema import (
    SchemaCatalog,
    TableSchema,
    ColumnSchema,
    ForeignKeySchema,
    parse_ddl_to_catalog,
    inspect_postgres_schema,
    DDLParseError,
    ReservedNamespaceError,
    SchemaTooLargeError,
    InvalidHintsError,
)


def test_schema_catalog_data_structure():
    catalog = SchemaCatalog(dialect="postgres")
    table = TableSchema(
        name="customers",
        columns=[
            ColumnSchema(name="id", data_type="INTEGER", is_primary_key=True, is_nullable=False),
            ColumnSchema(name="email", data_type="VARCHAR(255)", is_nullable=False),
        ],
        primary_keys=["id"]
    )
    catalog.tables["customers"] = table

    assert catalog.has_table("customers")
    assert catalog.has_table("CUSTOMERS")
    assert catalog.get_table("customers").name == "customers"
    assert catalog.total_foreign_keys() == 0

    prompt_str = catalog.to_prompt_string()
    assert "SCHEMA CATALOG" in prompt_str
    assert "TABLE customers:" in prompt_str
    assert "id: INTEGER NOT NULL [PK]" in prompt_str


def test_parse_postgres_ddl():
    ddl = """
    CREATE TYPE user_role AS ENUM ('admin', 'editor', 'viewer');

    CREATE TABLE users (
        user_id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        role user_role DEFAULT 'viewer'
    );

    CREATE TABLE posts (
        post_id SERIAL PRIMARY KEY,
        author_id INT NOT NULL REFERENCES users(user_id),
        title VARCHAR(200) NOT NULL,
        content TEXT
    );

    CREATE INDEX idx_posts_author ON posts(author_id);
    """

    catalog = parse_ddl_to_catalog(ddl, dialect="postgres")
    assert catalog.dialect == "postgres"
    assert len(catalog.tables) == 2
    assert catalog.has_table("users")
    assert catalog.has_table("posts")

    users_tbl = catalog.get_table("users")
    assert users_tbl.primary_keys == ["user_id"]
    role_col = users_tbl.get_column("role")
    assert role_col is not None
    assert role_col.enum_values == ["admin", "editor", "viewer"]

    posts_tbl = catalog.get_table("posts")
    assert len(posts_tbl.foreign_keys) == 1
    assert posts_tbl.foreign_keys[0].column == "author_id"
    assert posts_tbl.foreign_keys[0].ref_table == "users"

    # Index statement should be noted in warnings
    assert any("Skipped unsupported statements" in w for w in catalog.warnings)


def test_parse_mysql_ddl():
    mysql_ddl = """
    CREATE TABLE `categories` (
        `id` int NOT NULL AUTO_INCREMENT,
        `name` varchar(100) NOT NULL,
        PRIMARY KEY (`id`)
    ) ENGINE=InnoDB;

    CREATE TABLE `products` (
        `id` int NOT NULL AUTO_INCREMENT,
        `category_id` int NOT NULL,
        `name` varchar(255) NOT NULL,
        `status` enum('draft','published','archived') DEFAULT 'draft',
        PRIMARY KEY (`id`),
        CONSTRAINT `fk_product_category` FOREIGN KEY (`category_id`) REFERENCES `categories` (`id`)
    ) ENGINE=InnoDB;
    """

    catalog = parse_ddl_to_catalog(mysql_ddl, dialect="mysql")
    assert catalog.dialect == "mysql"
    assert len(catalog.tables) == 2
    assert catalog.has_table("categories")
    assert catalog.has_table("products")

    products_tbl = catalog.get_table("products")
    status_col = products_tbl.get_column("status")
    assert status_col is not None
    assert status_col.enum_values == ["draft", "published", "archived"]

    assert len(products_tbl.foreign_keys) == 1
    assert products_tbl.foreign_keys[0].ref_table == "categories"


def test_parse_ddl_with_valid_hints():
    ddl = """
    CREATE TABLE orders (
        id INT PRIMARY KEY,
        status VARCHAR(50) NOT NULL,
        total DECIMAL(10,2) NOT NULL
    );
    """
    hints = {
        "enums": {"orders.status": ["pending", "shipped", "delivered"]},
        "metrics": {"total_revenue": "SUM(orders.total)"},
        "notes": "All orders are in INR currency."
    }

    catalog = parse_ddl_to_catalog(ddl, dialect="postgres", hints=hints)
    orders_tbl = catalog.get_table("orders")
    status_col = orders_tbl.get_column("status")
    assert status_col.enum_values == ["pending", "shipped", "delivered"]
    assert catalog.hints.metrics["total_revenue"] == "SUM(orders.total)"
    assert catalog.hints.notes == "All orders are in INR currency."


def test_parse_ddl_errors():
    # 1. Invalid DDL syntax / no create table
    with pytest.raises(DDLParseError):
        parse_ddl_to_catalog("SELECT * FROM users;", dialect="postgres")

    # 2. Reserved namespace
    reserved_ddl = "CREATE TABLE sys.internal_log (id INT PRIMARY KEY);"
    with pytest.raises(ReservedNamespaceError):
        parse_ddl_to_catalog(reserved_ddl, dialect="postgres")

    # 3. Schema too large (> 15 tables)
    large_ddl = "\n".join([f"CREATE TABLE t_{i} (id INT PRIMARY KEY);" for i in range(16)])
    with pytest.raises(SchemaTooLargeError):
        parse_ddl_to_catalog(large_ddl, dialect="postgres")

    # 4. Invalid hint column reference
    simple_ddl = "CREATE TABLE users (id INT PRIMARY KEY);"
    bad_hints = {"enums": {"users.non_existent_col": ["a", "b"]}}
    with pytest.raises(InvalidHintsError):
        parse_ddl_to_catalog(simple_ddl, dialect="postgres", hints=bad_hints)


def test_postgres_inspector_mock():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    # Mock database inspection queries
    # 1. Tables query
    mock_cur.fetchall.side_effect = [
        [("categories",), ("products",)],  # table names
        [("categories", "id"), ("products", "id")],  # primary keys
        [("products", "category_id", "categories", "id")],  # foreign keys
        [],  # enums
        [("id", "integer", "int4", "NO", None), ("name", "character varying", "varchar", "NO", None)],  # categories cols
        [("id", "integer", "int4", "NO", None), ("category_id", "integer", "int4", "NO", None), ("name", "character varying", "varchar", "NO", None)],  # products cols
    ]

    catalog = inspect_postgres_schema(mock_conn, schema_name="demo")
    assert catalog.dialect == "postgres"
    assert catalog.has_table("categories")
    assert catalog.has_table("products")

    products_tbl = catalog.get_table("products")
    assert len(products_tbl.foreign_keys) == 1
    assert products_tbl.foreign_keys[0].ref_table == "categories"
