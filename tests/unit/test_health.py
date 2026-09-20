from coldchain.application.health import ReadinessService


class FailingProbe:
    async def ping(self) -> None:
        raise ConnectionError("internal detail must not leave the service")


async def test_readiness_hides_probe_exception() -> None:
    result = await ReadinessService(FailingProbe()).check()
    assert result.ready is False
    assert result.checks == {"database": "unavailable"}
