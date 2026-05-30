from datetime import date, time, timedelta

from models.appointment import Appointment


def _appt(day=date(2026, 5, 29)):
    # 2026-05-29 is a Friday
    return Appointment(
        day=day,
        entry_time=time(9, 1),
        lunch_start=time(12, 5),
        lunch_end=time(13, 6),
        exit_time=time(18, 2),
    )


def test_week_day_is_derived_from_day():
    assert _appt(date(2026, 5, 25)).week_day == 0  # Monday
    assert _appt(date(2026, 5, 29)).week_day == 4  # Friday
    assert _appt(date(2026, 5, 30)).week_day == 5  # Saturday


def test_get_all_intervals():
    intervals = _appt().get_all_intervals()
    assert intervals["morning"] == timedelta(hours=3, minutes=4)
    assert intervals["lunch"] == timedelta(hours=1, minutes=1)
    assert intervals["afternoon"] == timedelta(hours=4, minutes=56)


def test_total_working_hours_excludes_lunch():
    # Previously this method was broken (indexed a timedelta); guard against it.
    total = _appt().total_working_hours()
    assert total == timedelta(hours=8)


def test_lunch_interval():
    assert _appt().get_lunch_interval() == timedelta(hours=1, minutes=1)


def test_equality_includes_day_and_osi():
    a = _appt(date(2026, 5, 29))
    b = _appt(date(2026, 5, 29))
    assert a == b
    c = _appt(date(2026, 5, 28))
    assert a != c
