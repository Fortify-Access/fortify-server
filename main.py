import contextlib
import asyncio
from starlette.applications import Starlette
from starlette.routing import Route
from api.middleware import TokenAuthMiddleware
from api import endpoints
from api import tasks
from api import extentions

@contextlib.asynccontextmanager
async def lifespan(app):
    asyncio.create_task(tasks.check_expirations(300))
    asyncio.create_task(tasks.check_traffic_usages())
    asyncio.create_task(tasks.commit_traffic_usages_to_db(5))
    yield

app = Starlette(
    debug=True,
    routes=[
        Route("/inbound/list", endpoint=endpoints.inbound_list, methods=["GET"]),
        Route("/inbound/get", endpoint=endpoints.inbound_get, methods=["GET"]),
        Route("/inbound/get_last_updates", endpoint=endpoints.inbound_get_last_updates, methods=["GET"]),
        Route("/inbound/create", endpoint=endpoints.inbound_create, methods=["POST"]),
        Route("/inbound/update", endpoint=endpoints.inbound_create, methods=["PUT"]),
        Route("/inbound/delete", endpoint=endpoints.inbound_delete, methods=["DELETE"]),
    ],
    middleware=[(TokenAuthMiddleware, {})],
    lifespan=lifespan
)

if __name__ == "__main__":
    import uvicorn
    from sqlmodel import SQLModel
    from api import models
    from api.extentions import engine

    SQLModel.metadata.create_all(engine)
    uvicorn.run(app, host="0.0.0.0", port=extentions.API_PORT)

