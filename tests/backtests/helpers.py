import json
import logging
import pprint
import shutil
import subprocess
from types import SimpleNamespace

import attr

from tests.conftest import REPO_ROOT

log = logging.getLogger(__name__)


@attr.s(frozen=True)
class ProcessResult:
    """
    This class serves the purpose of having a common result class which will hold the
    resulting data from a subprocess command.
    :keyword int exitcode:
        The exitcode returned by the process
    :keyword str stdout:
        The ``stdout`` returned by the process
    :keyword str stderr:
        The ``stderr`` returned by the process
    :keyword list,tuple cmdline:
        The command line used to start the process
    .. admonition:: Note
        Cast :py:class:`~saltfactories.utils.processes.ProcessResult` to a string to pretty-print it.
    """

    exitcode = attr.ib()
    stdout = attr.ib()
    stderr = attr.ib()
    cmdline = attr.ib(default=None, kw_only=True)

    @exitcode.validator
    def _validate_exitcode(self, attribute, value):
        if not isinstance(value, int):
            raise ValueError(f"'exitcode' needs to be an integer, not '{type(value)}'")

    def __str__(self):
        message = self.__class__.__name__
        if self.cmdline:
            message += f"\n Command Line: {self.cmdline}"
        if self.exitcode is not None:
            message += f"\n Exitcode: {self.exitcode}"
        if self.stdout or self.stderr:
            message += "\n Process Output:"
        if self.stdout:
            message += f"\n   >>>>> STDOUT >>>>>\n{self.stdout}\n   <<<<< STDOUT <<<<<"
        if self.stderr:
            message += f"\n   >>>>> STDERR >>>>>\n{self.stderr}\n   <<<<< STDERR <<<<<"
        return message + "\n"


class Backtest:
    def __init__(self, request, exchange=None):
        self.request = request
        self.exchange = exchange

    def __call__(
        self,
        start_date,
        end_date,
        pairlist=None,
        max_open_trades=5,
        stake_amount="unlimited",
        exchange=None,
    ):
        if exchange is None:
            exchange = self.exchange
        if exchange is None:
            raise RuntimeError(
                f"No 'exchange' was passed when instantiating {self.__class__.__name__} or when calling it"
            )
        tmp_path = self.request.getfixturevalue("tmp_path")
        exchange_config = f"user_data/data/{exchange}-usdt-static.json"
        json_results_file = tmp_path / "backtest-results.json"
        cmdline = [
            "freqtrade",
            "backtesting",
            f"--user-data=user_data",
            "--strategy-list=NostalgiaForInfinityNext",
            f"--timerange={start_date}-{end_date}",
            f"--max-open-trades={max_open_trades}",
            f"--stake-amount={stake_amount}",
            "--config=user_data/data/pairlists.json",
        ]
        if pairlist is None:
            cmdline.append(f"--config={exchange_config}")
        else:
            pairlist_config = {"exchange": {"name": exchange, "pair_whitelist": pairlist}}
            pairlist_config_file = tmp_path / "test-pairlist.json"
            pairlist_config_file.write(json.dumps(pairlist_config))
            cmdline.append(f"--config={pairlist_config_file}")
        cmdline.append(f"--export-filename={json_results_file}")
        log.info("Running cmdline '%s' on '%s'", " ".join(cmdline), REPO_ROOT)
        proc = subprocess.run(
            cmdline, check=False, shell=False, cwd=REPO_ROOT, text=True, capture_output=True
        )
        ret = ProcessResult(
            exitcode=proc.returncode,
            stdout=proc.stdout.strip(),
            stderr=proc.stderr.strip(),
            cmdline=cmdline,
        )
        log.info("Command Result:\n%s", ret)
        assert ret.exitcode == 0
        generated_results_file = list(tmp_path.rglob("backtest-results-*.json"))[0]
        if self.request.config.option.artifacts_path:
            generated_json_results_artifact_path = (
                self.request.config.option.artifacts_path / generated_results_file.name
            )
            shutil.copyfile(generated_results_file, generated_json_results_artifact_path)
            generated_txt_results_artifact_path = generated_json_results_artifact_path.with_suffix(
                ".txt"
            )
            generated_txt_results_artifact_path.write_text(ret.stdout.strip())

        results_data = json.loads(generated_results_file.read_text())
        full_stats_data = results_data["strategy_comparison"][0]
        full_results_data = results_data["strategy"]["NostalgiaForInfinityNext"]
        data = {
            "stdout": ret.stdout.strip(),
            "stderr": ret.stderr.strip(),
            "results": full_results_data,
            "full_stats": full_stats_data,
            "stats_pct": {
                "max_drawdown": full_results_data["max_drawdown"] * 100,
                "winrate": round(full_stats_data["wins"] * 100.0 / full_stats_data["trades"], 2),
            },
        }
        # At some point, consider logging at the debug level or removing this log call
        # which is only here to understand the JSON results data structure.
        log_data = {}
        for key in ("results", "full_stats", "stats_pct"):
            log_data[key] = data[key]
        log.info(
            "Backtest results:\n%s",
            pprint.pformat(log_data),
        )
        return json.loads(json.dumps(data), object_hook=lambda d: SimpleNamespace(**d))


@attr.s(frozen=True)
class Timerange:
    start_date = attr.ib()
    end_date = attr.ib()


@attr.s(frozen=True)
class Exchange:
    name = attr.ib()
    winrate = attr.ib()
    max_drawdown = attr.ib()
