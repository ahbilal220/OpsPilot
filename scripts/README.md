# Foundation scripts

- `check_migrations.py`: round-trip Alembic on a separate disposable PostgreSQL database.
- `smoke.py`: test a running local Compose stack through the frontend API proxy.
- `install-docker-ubuntu.sh`: optional Docker Engine/Compose installer for Ubuntu;
  run with sudo in your own terminal. Uses Docker's official signed apt repository.

Neither script is exposed to agents or callable through the application.
