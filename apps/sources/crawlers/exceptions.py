"""Custom crawler exceptions."""


class CrawlCancelled(Exception):
    """Raised when a crawl is cancelled or paused externally."""

    def __init__(self, reason: str | None = None):
        super().__init__(reason or "Cancelled")
        self.reason = reason or "Cancelled"
