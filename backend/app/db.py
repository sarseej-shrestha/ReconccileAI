from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.models import Base


class Database:
    def __init__(self, url: str):
        if not url.startswith("sqlite:"):
            raise ValueError("This prototype supports SQLite; see PostgreSQL migration notes.")
        self.engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 15})

        @event.listens_for(self.engine, "connect")
        def configure(connection, _):
            connection.isolation_level = None
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=15000")
            connection.execute("PRAGMA journal_mode=WAL")

        @event.listens_for(self.engine, "begin")
        def begin(connection):
            mode = connection.get_execution_options().get("write_transaction", False)
            connection.exec_driver_sql("BEGIN IMMEDIATE" if mode else "BEGIN")

    def initialize(self):
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self, *, write=False):
        with self.engine.connect().execution_options(write_transaction=write) as connection:
            with Session(connection, expire_on_commit=False) as session, session.begin():
                yield session
