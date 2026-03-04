from sqlalchemy import Engine, text


def load_database_info(engine: Engine) -> tuple[str, str, str]:
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT version() AS server_version, current_database() AS database_name")
        ).mappings().one()

    driver = engine.dialect.name
    server_version = str(row["server_version"])
    database_name = str(row["database_name"])
    return driver, server_version, database_name
