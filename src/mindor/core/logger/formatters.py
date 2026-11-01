from typing import Optional
import logging, sys, click

_LEVEL_COLORS = {
    logging.DEBUG:    "cyan",
    logging.INFO:     "green",
    logging.WARNING:  "yellow",
    logging.ERROR:    "red",
    logging.CRITICAL: "bright_red",
}

class ColourizedFormatter(logging.Formatter):
    def __init__(self, fmt: Optional[str] = None, use_colors: Optional[bool] = None):
        super().__init__(fmt=fmt)

        self.use_colors = use_colors if use_colors is not None else sys.stderr.isatty()

    def formatMessage(self, record: logging.LogRecord) -> str:
        levelname = record.levelname
        separator = " " * (8 - len(levelname))

        if self.use_colors:
            color = _LEVEL_COLORS.get(record.levelno)

            if color is not None:
                levelname = click.style(levelname, fg=color)

        record.__dict__["levelprefix"] = levelname + ":" + separator

        return super().formatMessage(record)
