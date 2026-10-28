from redis.asyncio import Redis


def create_redis_client(redis_url: str) -> Redis:
    """Create the Redis connection used for runtime coordination."""

    return Redis.from_url(redis_url, decode_responses=True)
