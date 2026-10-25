import os

import pytest

from testbridge.studio.search_openalex import OpenAlexSearch

pytestmark = pytest.mark.live

requires_live = pytest.mark.skipif(
    os.environ.get("TESTBRIDGE_LIVE") != "1",
    reason="set TESTBRIDGE_LIVE=1 to run live OpenAlex tests",
)


@requires_live
def test_openalex_returns_hits() -> None:
    search = OpenAlexSearch(
        mailto=os.environ.get("TESTBRIDGE_OPENALEX_MAILTO") or None
    )

    hits = search.search("vision language action robot", count=3)

    assert hits
    assert all(hit.url.startswith("http") for hit in hits)
