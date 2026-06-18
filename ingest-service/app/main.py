import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import async_session_maker, close_db
from app.services.publisher import get_publisher, publish_outbox
from app.views import router as events_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    publisher = get_publisher()
    try:
        await publisher.connect()
    except Exception:
        pass

    outbox_task = None
    try:
        outbox_task = asyncio.create_task(publish_outbox(publisher, async_session_maker))
    except Exception:
        pass

    yield

    if outbox_task:
        outbox_task.cancel()
        try:
            await outbox_task
        except asyncio.CancelledError:
            pass
    await publisher.close()
    await close_db()


app = FastAPI(title="Ingest Service", lifespan=lifespan)
app.include_router(events_router, prefix="/api/v1")
