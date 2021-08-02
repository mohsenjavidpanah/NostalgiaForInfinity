import pytest

from tests.backtests.helpers import Backtest
from tests.backtests.helpers import Exchange
from tests.backtests.helpers import Timerange
from tests.conftest import REPO_ROOT


def exchange_fmt(value):
    return value.name


@pytest.fixture(
    scope="session",
    params=(
        Exchange(name="binance", winrate=90, max_drawdown=30),
        Exchange(name="kucoin", winrate=90, max_drawdown=30),
    ),
    ids=exchange_fmt,
)
def exchange(request):
    return request.param


@pytest.fixture(scope="session", autouse=True)
def check_exchange_data_presen(exchange):
    exchange_data_dir = REPO_ROOT / "user_data" / "data" / exchange.name
    if not exchange_data_dir.is_dir():
        pytest.fail(
            f"There's no exchange data for {exchange.name}. Make sure the repository submodule "
            "is init/update. Check the repository README.md for more information."
        )
    if not list(exchange_data_dir.rglob("*.json.gz")):
        pytest.fail(
            f"There's no exchange data for {exchange.name}. Make sure the repository submodule "
            "is init/update. Check the repository README.md for more information."
        )


@pytest.fixture
def backtest(request):
    return Backtest(request)


def timerange_fmt(value):
    return f"{value.start_date}-{value.end_date}"


@pytest.fixture(
    params=(
        Timerange("20210101", "20210201"),
        Timerange("20210201", "20210301"),
        Timerange("20210301", "20210401"),
        Timerange("20210401", "20210501"),
        Timerange("20210501", "20210601"),
        Timerange("20210601", "20210701"),
    ),
    ids=timerange_fmt,
)
def timerange(request):
    return request.param


def test_excpected_values(backtest, timerange, exchange):
    ret = backtest(
        start_date=timerange.start_date, end_date=timerange.end_date, exchange=exchange.name
    )
    assert ret.stats_pct.winrate >= exchange.winrate
    assert ret.stats_pct.max_drawdown <= exchange.max_drawdown
