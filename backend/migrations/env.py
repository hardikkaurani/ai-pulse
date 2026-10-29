from alembic import context
from app.db import engine, Base
from app import models  # noqa: F401 - register tables in Base.metadata

if context.is_offline_mode():
    raise RuntimeError("Run migrations online against the configured database.")
with engine.connect() as connection:
    context.configure(
        connection=connection, target_metadata=Base.metadata, render_as_batch=True
    )
    with context.begin_transaction():
        context.run_migrations()
