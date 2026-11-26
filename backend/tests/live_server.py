"""Local-only server fixture. Fault injection exists only in this test entry point."""

import os
from pathlib import Path
import socket
import threading

import uvicorn


def main():
    from backend.app.core.enums import Role
    from backend.app.database import SessionLocal, init_db
    from backend.app.repositories import user_repo
    from engine import interface

    init_db()
    with SessionLocal() as db:
        for name, role in (("qa_admin", Role.ADMIN), ("qa_operator", Role.OPERATOR), ("qa_viewer", Role.VIEWER)):
            if user_repo.get_by_username(db, name) is None:
                user_repo.create_user(db, name, os.environ["SIDEWATCH_TEST_PASSWORD"], role)

    real_analysis = interface.run_analysis

    def controlled_analysis(request):
        if request.fixture_id == "prefix_1":
            raise RuntimeError("PRIVATE_ENGINE_DETAIL_FOR_TEST")
        if request.fixture_id == "prefix_4":
            return {"reasons": [], "private": "PRIVATE_ENGINE_DETAIL_FOR_TEST"}
        if request.fixture_id == "full_match":
            Path(os.environ["SIDEWATCH_TEST_MARKER"]).write_text("engine entered", encoding="utf-8")
            threading.Event().wait()  # parent kills this process to test crash recovery
        return real_analysis(request)

    interface.run_analysis = controlled_analysis
    # Bind port zero in the child: no free-port race or fixed port dependency.
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        Path(os.environ["SIDEWATCH_TEST_PORT"]).write_text(str(port), encoding="ascii")
        config = uvicorn.Config("backend.app.main:app", host="127.0.0.1", port=port,
                                log_level="warning", access_log=False)
        uvicorn.Server(config).run(sockets=[listener])


if __name__ == "__main__":
    main()
