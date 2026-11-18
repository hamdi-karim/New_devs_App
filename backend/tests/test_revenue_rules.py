from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.services.revenue_rules import month_bounds_utc, revenue_cache_key, round_money

UTC = timezone.utc


# --- round_money ---------------------------------------------------------


def test_round_money_sums_thirds_to_exact_total():
    total = Decimal("333.333") + Decimal("333.333") + Decimal("333.334")
    assert round_money(total) == Decimal("1000.00")


def test_round_money_rounds_half_up():
    assert round_money(Decimal("2.675")) == Decimal("2.68")


def test_round_money_rounds_half_cent_up():
    assert round_money(Decimal("0.005")) == Decimal("0.01")


def test_round_money_has_exactly_two_decimal_places():
    result = round_money(Decimal("5"))
    assert result == Decimal("5.00")
    assert result.as_tuple().exponent == -2


def test_float_sum_drifts_but_decimal_sum_is_exact():
    # Documents the cents bug: float arithmetic before rounding is lossy.
    assert 0.1 + 0.2 != 0.3
    assert round_money(Decimal("0.1") + Decimal("0.2")) == Decimal("0.30")


# --- revenue_cache_key ---------------------------------------------------


def test_revenue_cache_key_format():
    assert revenue_cache_key("tenant-a", "prop-001") == "revenue:v2:tenant-a:prop-001"


def test_revenue_cache_key_differs_per_tenant_for_same_property():
    assert revenue_cache_key("tenant-a", "prop-001") != revenue_cache_key("tenant-b", "prop-001")


# --- month_bounds_utc ----------------------------------------------------


def test_month_bounds_paris_march_2024_handles_dst_switch():
    assert month_bounds_utc(2024, 3, "Europe/Paris") == (
        datetime(2024, 2, 29, 23, 0, tzinfo=UTC),
        datetime(2024, 3, 31, 22, 0, tzinfo=UTC),
    )


def test_month_bounds_new_york_march_2024():
    assert month_bounds_utc(2024, 3, "America/New_York") == (
        datetime(2024, 3, 1, 5, 0, tzinfo=UTC),
        datetime(2024, 4, 1, 4, 0, tzinfo=UTC),
    )


def test_month_bounds_december_rolls_over_to_next_year():
    _, end = month_bounds_utc(2024, 12, "Europe/Paris")
    assert end == datetime(2024, 12, 31, 23, 0, tzinfo=UTC)


def test_month_bounds_are_aware_utc():
    start, end = month_bounds_utc(2024, 3, "Europe/Paris")
    assert start.utcoffset() == timedelta(0)
    assert end.utcoffset() == timedelta(0)


def test_seed_checkin_res_tz_1_is_in_paris_march_not_utc_march():
    check_in = datetime(2024, 2, 29, 23, 30, tzinfo=UTC)  # res-tz-1

    paris_start, paris_end = month_bounds_utc(2024, 3, "Europe/Paris")
    utc_start, utc_end = month_bounds_utc(2024, 3, "UTC")

    assert paris_start <= check_in < paris_end
    assert not (utc_start <= check_in < utc_end)


def test_month_bounds_end_is_exclusive():
    march_start, march_end = month_bounds_utc(2024, 3, "Europe/Paris")
    april_start, april_end = month_bounds_utc(2024, 4, "Europe/Paris")
    check_in = datetime(2024, 3, 31, 22, 0, tzinfo=UTC)  # 2024-04-01 00:00 Paris

    assert not (march_start <= check_in < march_end)
    assert april_start <= check_in < april_end
