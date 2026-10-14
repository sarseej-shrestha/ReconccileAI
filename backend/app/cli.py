"""Local demo lifecycle. Reset is deliberately unavailable over HTTP."""

import argparse
import json
from pathlib import Path
from uuid import uuid4

from app.config import Settings
from app.db import Database
from app.models import Base
from app.schemas import ImportData
from app.services.importing import import_data


def main():
    parser = argparse.ArgumentParser(description="ReconcileAI fictional demo database")
    parser.add_argument("command", choices=["init", "load", "reset"])
    parser.add_argument(
        "--yes", action="store_true", help="Confirm deletion of all demo records and audit history"
    )
    args = parser.parse_args()
    db = Database(Settings().database_url)
    if args.command == "reset":
        if not args.yes:
            parser.error("reset deletes the local demo database contents; pass --yes to confirm")
        Base.metadata.drop_all(db.engine)
    db.initialize()
    if args.command != "init":
        fixture = Path(__file__).resolve().parents[2] / "data/synthetic/records.json"
        with db.session(write=True) as session:
            print(
                json.dumps(
                    import_data(
                        session, ImportData.model_validate_json(fixture.read_text()), str(uuid4())
                    )
                )
            )
    else:
        print("Database initialized")
    db.engine.dispose()


if __name__ == "__main__":
    main()
