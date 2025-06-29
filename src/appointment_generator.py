from __future__ import annotations
from typing import Literal
import random
from datetime import datetime, time, timedelta

################################################################################
### Utility

def same_minute(a: time, b: time) -> bool:
    return a.minute == b.minute

################################################################################
#### Appointment Class

class Appointment:
    """
    Represents a workday appointment with entry, lunch start, lunch end, and exit times.
    """
    def __init__(self, entry_time: time, lunch_start_time: time, lunch_end_time: time, exit_time: time):
        self.entry = entry_time
        self.lunch_start = lunch_start_time
        self.lunch_end = lunch_end_time
        self.exit = exit_time


    def get_lunch_interval(self) -> timedelta:
        dt_lunch_start = datetime.combine(datetime.today(), self.lunch_start)
        dt_lunch_end = datetime.combine(datetime.today(), self.lunch_end)
        return dt_lunch_end - dt_lunch_start
    
    

    def get_all_intervals(self) -> dict[
        Literal["morning", "lunch", "afternoon"], 
        timedelta
    ]:
        """
        Returns duration deltas for:
          - morning (entry to lunch_start)
          - lunch (lunch_start to lunch_end)
          - afternoon (lunch_end to exit)
        """
        dt_entry = datetime.combine(datetime.today(), self.entry)
        dt_lunch_start = datetime.combine(datetime.today(), self.lunch_start)
        dt_lunch_end = datetime.combine(datetime.today(), self.lunch_end)
        dt_exit = datetime.combine(datetime.today(), self.exit)

        return {
            'morning': dt_lunch_start - dt_entry,
            'lunch': dt_lunch_end - dt_lunch_start,
            'afternoon': dt_exit - dt_lunch_end
        }


    def total_working_hours(self) -> timedelta:
        """
        Returns total working time (morning + afternoon), excluding lunch.
        """
        intervals = self.get_lunch_interval()
        return intervals['morning'] + intervals['afternoon']


    def __eq__(self, other):
        if not isinstance(other, Appointment):
            return False
        return (self.entry == other.entry and
                self.lunch_start == other.lunch_start and
                self.lunch_end == other.lunch_end and
                self.exit == other.exit)


    def __repr__(self):
        return (f"Appointment(entry={self.entry.strftime('%H:%M')}, lunch_start={self.lunch_start.strftime('%H:%M')}, "
                f"lunch_end={self.lunch_end.strftime('%H:%M')}, exit={self.exit.strftime('%H:%M')})")


    ############################################################################
    #### Utility

    @staticmethod
    def generate_appointment(history: list[Appointment]) -> Appointment:
        """
        Generates a new Appointment valid under both initial and new rules,
        considering up to 5 previous entries.
        """
        last_week = history[-5:]
        attempts = 0
        while attempts < 1000:
            # Entry time
            entry_hour = random.choice([8, 9])
            entry_min = random.randint(1, 59)
            entry_time = time(entry_hour, entry_min)

            # Lunch start
            lunch_start_hour = random.choice([12, 13, 14])
            lunch_start_min = random.randint(1, 59)
            lunch_start = time(lunch_start_hour, lunch_start_min)

            # Lunch end = lunch_start + at least 60m plus up to 15m flex
            lunch_duration = timedelta(hours=1, minutes=random.randint(0, 15))
            dt_lunch_end = (datetime.combine(datetime.today(), lunch_start) + lunch_duration)
            lunch_end = dt_lunch_end.time()

            # Exit time
            exit_hour = random.choice([17, 18])
            ## Compute afternoon duration to fit total span approx
            ## span_target = span between entry and exit around 9h+ to 10h+
            exit_min = random.randint(1, 59)
            exit_time = time(exit_hour, exit_min)

            # Create appointment object
            appt = Appointment(entry_time, lunch_start, lunch_end, exit_time)

            if Appointment.is_valid(appt, last_week):
                return appt
            
            attempts += 1
        
        raise RuntimeError("Could not generate a valid appointment after many attempts.")
    
    @staticmethod
    def is_valid(appointment: Appointment, history: list[Appointment]) -> bool:
        """
        True if its valid, False otherwise.

        Validates rules:
        1. Entry and exit minutes differ
        2. Entry and lunch_start minutes differ
        3. Lunch_end and exit minutes differ
        4. No identical exact shifts in the history
        5. No minutes ending with 00
        6. Exit hour must be 17 or 18
        7. Entry hour must be 8 or 9
        8. Lunch >= 1h
        9. Lunch start hour in {12, 13, 14}
        10. Total work approx (9 to 18) flexible with 1h lunch
        """

        # Minutes comparisons per field
        if same_minute(appointment.entry, appointment.exit):
            return False
        if same_minute(appointment.entry, appointment.lunch_start):
            return False
        if same_minute(appointment.lunch_end, appointment.exit):
            return False
        
        # Unique per field in history
        for past in history:
            if same_minute(appointment.entry, past.entry):
                return False
            if same_minute(appointment.lunch_start, past.lunch_start):
                return False
            if same_minute(appointment.lunch_end, past.lunch_end):
                return False
            if same_minute(appointment.exit, past.exit):
                return False

        # Rule 5
        for t in [appointment.entry, appointment.lunch_start, 
                  appointment.lunch_end, appointment.exit]:
            if t.minute == 0:
                return False
            
        # Rule 6 & 7
        if appointment.exit.hour not in (17, 18):
            return False
        if appointment.entry.hour not in (8, 9):
            return False
        
        # Rule 8 & 9
        lunch_interval = appointment.get_lunch_interval()
        if lunch_interval < timedelta(hours=1):
            return False
        if appointment.lunch_start.hour not in (12, 13, 14):
            return False
        
        # Rule 10: Total span from entry to exit approx 9h or 10h
        span = datetime.combine(datetime.today(), appointment.exit) - datetime.combine(datetime.today(), appointment.entry)
        if span < timedelta(hours=9) or span > timedelta(hours=10):
            return False


        return True


    @staticmethod
    def is_list_valid(appts: list[Appointment]) -> bool:
        """
        Checks a list of appointments against all rules.
        Returns True if all valid.
        """
        history = []
        for appt in appts:
            if not Appointment.is_valid(appt, history):
                return False
            history.append(appt)
            
        return True
