import math
import time
from collections.abc import Callable
from types import TracebackType
from typing import Self, TextIO

import click
from rich.console import Console
from rich.live import Live
from rich.text import Text

from local_transcribe.domain.recording import InputDevice, InputLevel

BAR_WIDTH = 20
TERMINAL_INTERVAL = 0.1
REDIRECTED_INTERVAL = 1.0


class LevelDisplay:
    def __init__(
        self,
        devices: tuple[InputDevice, InputDevice],
        *,
        stream: TextIO | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._devices = devices
        self._stream = stream if stream is not None else click.get_text_stream("stdout")
        self._clock = clock
        self._interactive = self._stream.isatty()
        self._values = [0.0, 0.0]
        self._last_output = float("-inf")
        self._live: Live | None = None

    def __enter__(self) -> Self:
        if self._interactive:
            self._live = Live(
                self._render(),
                console=Console(file=self._stream, force_terminal=True),
                auto_refresh=False,
                redirect_stdout=False,
                redirect_stderr=False,
            )
            self._live.start(refresh=True)
            self._last_output = self._clock()
        else:
            self.update(())
        return self

    def update(self, snapshot: tuple[InputLevel, ...]) -> None:
        levels = {level.device_id: level.rms for level in snapshot}
        for index, device in enumerate(self._devices):
            rms = levels.get(device.id, 0.0)
            if not math.isfinite(rms) or rms <= 0.001:
                target = 0.0
            else:
                target = min(1.0, max(0.0, (math.log10(rms) + 3) / 3))
            smoothing = 0.6 if target > self._values[index] else 0.3
            self._values[index] += smoothing * (target - self._values[index])

        now = self._clock()
        interval = TERMINAL_INTERVAL if self._interactive else REDIRECTED_INTERVAL
        if now - self._last_output < interval:
            return
        renderable = self._render()
        if self._live is not None:
            self._live.update(renderable, refresh=True)
        else:
            self._stream.write(
                "Levels: " + renderable.plain.replace("\n", " | ") + "\n"
            )
            self._stream.flush()
        self._last_output = now

    def _render(self) -> Text:
        text = Text()
        for index, device in enumerate(self._devices):
            if index:
                text.append("\n")
            name = "".join(char if char.isprintable() else " " for char in device.name)
            filled = round(self._values[index] * BAR_WIDTH)
            text.append(f"{device.id}: {name} [")
            text.append("#" * filled, style="green")
            text.append("-" * (BAR_WIDTH - filled), style="dim")
            text.append("]")
        return text

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._live is not None:
            self._live.stop()
