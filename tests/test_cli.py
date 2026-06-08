from nxbak.cli import format_git_date, parse_git_date


def test_parse_git_date_orders_timezone_dates():
    newer = parse_git_date("2026-06-07 16:03:18 +0700")
    older = parse_git_date("2026-06-07 15:57:22 +0700")
    assert newer > older


def test_format_git_date_is_human_readable():
    assert format_git_date("2026-06-07 16:03:18 +0700") == "16:03:18 07-06-2026"
