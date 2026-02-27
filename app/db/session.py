from sqlalchemy import create_engine, text
from app.core.settings import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)

def get_db_info() -> dict[str, str]:
    with engine.connect() as conn:
        driver = engine.url.drivername
        server_version = conn.execute(text("select version()")).scalar_one()
        db_name = conn.execute(text("select current_database()")).scalar_one()

    return {
        "driver": driver,
        "server_version": server_version,
        "database": db_name,
    }