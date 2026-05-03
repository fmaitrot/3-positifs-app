from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = PROJECT_ROOT / "public"


def test_hidden_attribute_is_not_overridden_by_layout_classes() -> None:
    styles = (PUBLIC_DIR / "styles.css").read_text(encoding="utf-8")

    assert "[hidden]" in styles
    assert "display: none !important;" in styles


def test_private_views_are_hidden_before_authentication() -> None:
    html = (PUBLIC_DIR / "index.html").read_text(encoding="utf-8")

    expected_hidden_views = [
        'id="app-nav" class="panel app-nav" aria-label="Navigation principale" hidden',
        'id="entry-panel" class="panel" aria-labelledby="entry-title" hidden',
        'id="history-panel" class="panel" aria-labelledby="history-title" hidden',
        'id="calendar-panel" class="panel" aria-labelledby="calendar-title" hidden',
        'id="reminder-panel" class="panel" aria-labelledby="reminder-title" hidden',
    ]

    for expected_view in expected_hidden_views:
        assert expected_view in html
