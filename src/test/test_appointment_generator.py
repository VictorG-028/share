import sys
import os

import pytest
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.appointment_generator import Appointment
from datetime import time


def test_valid_sample_week():
    appointments = [
        Appointment(time(9, 1), time(12, 5), time(13, 6), time(18, 2)),
        Appointment(time(9, 2), time(12, 6), time(13, 7), time(18, 3)),
        Appointment(time(9, 3), time(12, 7), time(13, 8), time(18, 4)),
        Appointment(time(9, 4), time(12, 8), time(13, 9), time(18, 5)),
        Appointment(time(9, 5), time(12, 9), time(13, 10), time(18, 6)),
    ]
    assert Appointment.is_list_valid(appointments) == True


@pytest.mark.parametrize("entry_time, lunch_start, lunch_end, exit_time", [
    (time(9, 10), time(12, 10), time(13, 1), time(18, 2)),   # entry == lunch_start minutes
    (time(9, 9), time(12, 1), time(13, 9), time(18, 2)),     # entry == lunch_end minutes
    (time(9, 16), time(12, 1), time(13, 2), time(18, 16)),   # entry == exit minutes
    (time(9, 1), time(12, 23), time(13, 23), time(18, 2)),   # lunch_start == lunch_end minutes
    (time(9, 1), time(12, 24), time(13, 24), time(18, 2)),   # lunch_start == lunch_end minutes
    (time(9, 1), time(12, 32), time(13, 2), time(18, 32)),   # lunch_end == exit minutes
    (time(9, 1), time(12, 2), time(13, 56), time(18, 56)),   # lunch_start != others but lunch_end == exit minutes
])
def test_invalid_due_to_same_minutes_in_fields(entry_time, lunch_start, lunch_end, exit_time):
    a = Appointment(entry_time, lunch_start, lunch_end, exit_time)
    assert Appointment.is_valid(a, []) is False


def test_lunch_less_than_one_hour():
    a = Appointment(time(9, 10), time(12, 10), time(12, 59), time(18, 11))
    assert Appointment.is_valid(a, []) == False


def test_exit_hour_invalid():
    a = Appointment(time(9, 15), time(12, 10), time(13, 20), time(19, 10))  # 19h não permitido
    assert Appointment.is_valid(a, []) == False


def test_generate_returns_valid():
    sample_week = [
        Appointment(time(9, 1), time(12, 5), time(13, 6), time(18, 2)),
        Appointment(time(9, 2), time(12, 6), time(13, 7), time(18, 3)),
        Appointment(time(9, 3), time(12, 7), time(13, 8), time(18, 4)),
        Appointment(time(9, 4), time(12, 8), time(13, 9), time(18, 5)),
        Appointment(time(9, 5), time(12, 9), time(13, 10), time(18, 6)),
    ]
    new_appt = Appointment.generate_appointment(sample_week)
    assert Appointment.is_valid(new_appt, sample_week), "Sample week failed validation"
