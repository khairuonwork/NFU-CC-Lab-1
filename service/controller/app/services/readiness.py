import asyncpg
import httpx
from redis.asyncio import Redis

from controller.app.core.config import Settings

async def check_postgres(settings: Settings) -> str:
    if not settings.postgres_is_configured:
        return "unconfigured"

    try:
        connection = await asyncpg.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
            timeout=2,
        )

        try:
            database_result = await connection.fetchval("SELECT 1")

            if database_result == 1:
                return "ready"

            return "unhealthy"

        finally:
            await connection.close()

    except Exception:
        return "unreachable"

async def check_redis(settings: Settings) -> str:
    if not settings.redis_is_configured:
        return "unconfigured"

    redis_client = Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )

    try:
        if await redis_client.ping():
            return "ready"

        return "unhealthy"

    except Exception:
        return "unreachable"

    finally:
        await redis_client.aclose()


async def check_rustfs(settings: Settings) -> str:
    if not settings.rustfs_is_configured:
        return "unconfigured"

    try:
        async with httpx.AsyncClient(timeout=2) as client:
            response = await client.get(settings.rustfs_health_url)

        if response.is_success:
            return "ready"

        return "unhealthy"

    except httpx.HTTPError:
        return "unreachable"


async def read_dependency_health(settings: Settings) -> dict[str, str]:
    return {
        "postgres": await check_postgres(settings),
        "redis": await check_redis(settings),
        "rustfs": await check_rustfs(settings),
    }