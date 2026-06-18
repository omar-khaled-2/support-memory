import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import close_db
from app.services.consumer import get_consumer, run_consumer
from app.views import router as memory_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    consumer = get_consumer()
    consumer_task = None
    try:
        consumer_task = asyncio.create_task(run_consumer(consumer))
    except Exception:
        pass

    yield

    if consumer_task:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
    await consumer.close()
    await close_db()


app = FastAPI(title="Memory Service", lifespan=lifespan)
app.include_router(memory_router, prefix="/api/v1")
