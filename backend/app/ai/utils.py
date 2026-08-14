import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


async def map_limited(
    items: list,
    fn: Callable[..., Awaitable[T]],
    *,
    limit: int = 3,
) -> list[T]:
    """Run async fn over items with a concurrency cap."""
    if not items:
        return []
    sem = asyncio.Semaphore(max(1, limit))

    async def run(item):
        async with sem:
            return await fn(item)

    return list(await asyncio.gather(*[run(item) for item in items]))
