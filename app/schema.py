"""Database bootstrap and small in-place schema upgrades.

The app supports both SQLite (local development) and PostgreSQL (deployment).
``upgrade_schema`` creates any missing tables and adds columns introduced by
newer versions without dropping existing data, so it is safe to run on every
startup as well as once per deployment.
"""

from sqlalchemy import inspect, text

from . import db


def _table_names():
    return set(inspect(db.engine).get_table_names())


def _columns(table_name):
    return {column["name"] for column in inspect(db.engine).get_columns(table_name)}


def _add_column_if_missing(table_name, column_name, column_type):
    if column_name not in _columns(table_name):
        with db.engine.begin() as connection:
            connection.execute(
                text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
            )


def _scope_existing_data_to_owner():
    """Assign rows created before multi-user support to the original shop."""
    with db.engine.begin() as connection:
        owner_id = connection.execute(
            text("SELECT user_id FROM sales WHERE user_id IS NOT NULL ORDER BY id LIMIT 1")
        ).scalar()
        if owner_id is None:
            owner_id = connection.execute(
                text("SELECT id FROM users ORDER BY id LIMIT 1")
            ).scalar()
        if owner_id is None:
            return

        connection.execute(
            text("UPDATE products SET user_id = :owner_id WHERE user_id IS NULL"),
            {"owner_id": owner_id},
        )
        connection.execute(
            text("UPDATE customers SET user_id = :owner_id WHERE user_id IS NULL"),
            {"owner_id": owner_id},
        )


def _widen_password_hash():
    """PostgreSQL enforces VARCHAR lengths; older schemas used 128 chars.

    Werkzeug's scrypt hashes are ~162 characters, which SQLite stores happily
    but PostgreSQL rejects. Widen the column on databases created before the
    model was corrected.
    """
    if db.engine.dialect.name == "sqlite" or "users" not in _table_names():
        return

    columns = {column["name"]: column for column in inspect(db.engine).get_columns("users")}
    current = columns.get("password_hash")
    if current is None:
        return

    length = getattr(current["type"], "length", None)
    if length is not None and length < 255:
        if db.engine.dialect.name == "postgresql":
            with db.engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE users ALTER COLUMN password_hash TYPE VARCHAR(255)")
                )
        else:
            with db.engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE users MODIFY password_hash VARCHAR(255)")
                )


def _make_product_sku_unique_per_user():
    """SQLite stores the old global UNIQUE(sku); rebuild the table once.

    PostgreSQL databases created from the current models already have the
    composite ``uq_products_user_sku`` constraint, so this is SQLite-only.
    """
    if db.engine.dialect.name != "sqlite":
        return

    inspector = inspect(db.engine)
    unique_constraints = inspector.get_unique_constraints("products")
    unique_indexes = inspector.get_indexes("products")
    has_global_sku_unique = any(
        constraint.get("column_names") == ["sku"] for constraint in unique_constraints
    ) or any(
        index.get("unique") and index.get("column_names") == ["sku"]
        for index in unique_indexes
    )
    if not has_global_sku_unique:
        return

    with db.engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.exec_driver_sql("DROP TABLE IF EXISTS products_new")
        connection.exec_driver_sql(
            """
            CREATE TABLE products_new (
                id INTEGER NOT NULL,
                sku VARCHAR(64),
                name VARCHAR(200) NOT NULL,
                description TEXT,
                price NUMERIC(10, 2) NOT NULL,
                cost NUMERIC(10, 2),
                quantity_in_stock INTEGER,
                user_id INTEGER,
                category_id INTEGER,
                supplier_id INTEGER,
                PRIMARY KEY (id),
                CONSTRAINT uq_products_user_sku UNIQUE (user_id, sku),
                FOREIGN KEY(user_id) REFERENCES users (id),
                FOREIGN KEY(category_id) REFERENCES categories (id),
                FOREIGN KEY(supplier_id) REFERENCES suppliers (id)
            )
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO products_new (
                id, sku, name, description, price, cost,
                quantity_in_stock, user_id, category_id, supplier_id
            )
            SELECT
                id, sku, name, description, price, cost,
                quantity_in_stock, user_id, category_id, supplier_id
            FROM products
            """
        )
        connection.exec_driver_sql("DROP TABLE products")
        connection.exec_driver_sql("ALTER TABLE products_new RENAME TO products")
        connection.commit()


def upgrade_schema():
    """Create tables and apply the light-weight schema migrations."""
    db.create_all()

    tables = _table_names()
    if "users" in tables:
        _add_column_if_missing("users", "shop_name", "VARCHAR(200)")
    if "products" in tables:
        _add_column_if_missing("products", "user_id", "INTEGER")
    if "customers" in tables:
        _add_column_if_missing("customers", "user_id", "INTEGER")

    _widen_password_hash()
    _scope_existing_data_to_owner()
    _make_product_sku_unique_per_user()
