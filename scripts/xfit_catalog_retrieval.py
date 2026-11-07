"""Source-bound and age-verified product feed date for XFIT commercial guides.

Cites only when the partner catalog was fetched by our own authenticated job.
It never claims the merchant updated each price on that date, or that an item
was in stock. Invalid/stale/unknown timestamps stop live publication.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from scripts.wp_publish import PublishError

MAX_FEED_AGE = timedelta(hours=4)
FUTURE_TOLERANCE = timedelta(minutes=5)
PRAGUE = ZoneInfo("Europe/Prague")


def verified_catalog_fetch_time(catalog, *, now=None, required=False):
    if not isinstance(catalog, dict):
        raise PublishError("Invalid catalog metadata")
    raw = catalog.get("fetched_at_utc")
    if not raw:
        if required:
            raise PublishError("Missing verified catalog retrieval timestamp")
        return None
    if not isinstance(raw, str) or len(raw) > 60:
        raise PublishError("Invalid catalog retrieval timestamp")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, OverflowError) as exc:
        raise PublishError("Unparseable catalog retrieval timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise PublishError("Catalog retrieval timestamp must use UTC")
    observed = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(observed, datetime) or observed.tzinfo is None:
        raise PublishError("No trustworthy current time")
    delta = observed.astimezone(timezone.utc) - parsed.astimezone(timezone.utc)
    if delta < -FUTURE_TOLERANCE or delta > MAX_FEED_AGE:
        raise PublishError("Catalog retrieval is stale or from the future")
    return parsed.astimezone(timezone.utc)


def catalog_retrieval_notice(catalog, *, now=None):
    fetched = verified_catalog_fetch_time(catalog, now=now)
    if fetched is None:
        # Synthetic unit-test fixtures are allowed to omit metadata; production
        # CLI uses required=True before building or publishing any product offer.
        return ""
    local = fetched.astimezone(PRAGUE)
    displayed_date = f"{local.day}. {local.month}. {local.year}"
    return (
        '<p class="xfit-feed-retrieval"><small>'
        '<strong>Kdy jsme data nabídky načetli:</strong> ' +
        displayed_date +
        ' (produktový XML katalog NaMaximum.cz). '
        'Datum označuje načtení katalogu, nikoli okamžik změny ceny u prodejce. '
        'Aktuální cenu, složení a dostupnost ověřte v obchodě.'
        '</small></p>'
    )
