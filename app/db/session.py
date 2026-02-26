from sqlalchemy import create_engine, text
from app.core.settings import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)

def get_db_info() -> dict:
    with engine.connect() as conn:
        # драйвер берем из URL
        driver = engine.url.drivername

        # версия сервера
        server_version = conn.execute(text("select version()")).scalar_one()

        # имя текущей базы
        db_name = conn.execute(text("select current_database()")).scalar_one()

    return {
        "driver": driver,
        "server_version": server_version,
        "database": db_name,
    }