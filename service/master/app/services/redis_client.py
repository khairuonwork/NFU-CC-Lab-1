from redis.asyncio import Redis

# Create the Redis connection used for runtime coordination
def create_redis_client(redis_url: str) -> Redis:
    return Redis.from_url(redis_url, decode_responses=True)
