from datetime import time
from src.appointment_generator import Appointment

if __name__ == "__main__":
    
    sample_week = [
        Appointment(time(9,1), time(12,5), time(13,6), time(18,2)),
        Appointment(time(9,2), time(12,6), time(13,7), time(18,3)),
        Appointment(time(9,3), time(12,7), time(13,8), time(18,4)),
        Appointment(time(9,4), time(12,8), time(13,9), time(18,5)),
        Appointment(time(9,5), time(12,9), time(13,10), time(18,6)),
        Appointment(time(9,6), time(12,10), time(13,11), time(18,7)),
    ]
    assert Appointment.is_list_valid(sample_week), "Sample week failed validation"
    new_appt = Appointment.generate_appointment(sample_week)
    print("Generated:", new_appt)
