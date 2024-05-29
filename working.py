import time
from machine import Pin
import ujson as json
import sys
import os
import utime

manual_mode=Pin("LED",Pin.OUT)
# Pin configuration from Pin 0 to 8

pin_list = [Pin(i, Pin.OUT) for i in range(8)]
#setting button pins 
set_button=Pin(10,Pin.IN,pull=Pin.PULL_UP)
up_button=Pin(11,Pin.IN,pull=Pin.PULL_UP)
down_button=Pin(12,Pin.IN,pull=Pin.PULL_UP)
ok_button=Pin(13,Pin.IN,pull=Pin.PULL_UP)

#set mode button pins

mode_button=Pin(15,Pin.IN,pull=Pin.PULL_UP)

# initial mode
automatic_mode = True
# Initialize previous_work variable to keep track of the previous value of work
previous_work = None


#button veriables
setting_mode = False
adjusting_works = True

#off the job after sertain time
offing_time_end = 2
transition_duration = 0.5# Define desired offing time (in seconds)
last_pin_on_time = 0

# Constants
default_interval_seconds = 0
NUMBER_OF_WORK1 = 0
INTERVAL_SECONDS = [default_interval_seconds] * NUMBER_OF_WORK1
select_time_indices = [0] * NUMBER_OF_WORK1
work_index = 0

#button buffet set
setting_mode =False 
last_pressed_time = 0
buffer_time = 0.5

# Manual state variables
setting_mode = False
current_selection = 0
selected_pins = []

#setting the time
select_time = ["0:005","0:010","0:02","0:05", "0:10", "0:15", "0:30", "0:45", "1:00", "1:15", "1:30", "1:45", "2:00", 
               "2:15", "2:30", "2:45", "3:00", "3:15", "3:30", "3:45", "4:00", "4:15", "4:30", 
               "4:45", "5:00", "5:15", "5:30", "5:45", "6:00", "6:15", "6:30", "6:45", "7:00", 
               "7:15", "7:30", "7:45", "8:00", "8:15", "8:30", "8:45", "9:00", "9:15", "9:30", 
               "9:45", "10:00", "10:15", "10:30", "10:45", "11:00", "11:15", "11:30", "11:45", 
               "12:00"]

def toggle_mode(pin):
    global last_pressed_time
    current_time = utime.ticks_ms()  
    
    if current_time - last_pressed_time > buffer_time * 1000:
        last_pressed_time = current_time
        global automatic_mode
        automatic_mode = not automatic_mode


def load_state():
    try:
        with open('/store.ini', 'r') as f:
            data = json.load(f)
            last_execution_time = data["last_execution_time"]
            work = data["work"]
            interval_seconds = data["interval_seconds"]
            NUMBER_OF_WORK = data["NUMBER_OF_WORK"]
            return last_execution_time, work, interval_seconds, NUMBER_OF_WORK
    except (OSError, ValueError, IndexError):
        print("Error loading state.")
        return None, None, [], 0

def save_state(last_execution_time, work, interval_seconds, NUMBER_OF_WORK):
    data = {
        "last_execution_time": last_execution_time,
        "work": work,
        "interval_seconds": interval_seconds,
        "NUMBER_OF_WORK": NUMBER_OF_WORK
    }
    
    
    with open('/store.ini', 'w') as f:
        json.dump(data, f)
        
        
def time_to_seconds(time_str):
    parts = time_str.split(':')
    hours = int(parts[0])
    minutes = int(parts[1])
    total_seconds = hours * 3600 + minutes * 60
    
    return total_seconds

def seconds_to_timer(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    timer_format = f"{hours}:{minutes:02}:{seconds:02}"
    
    return timer_format


def print_handler(*args):
    output = ' '.join(map(str, args))
    print('\r' + output, end='')

def up_button_handler(pin):
    global last_pressed_time
    
    current_time = utime.ticks_ms()  
    
    if current_time - last_pressed_time > buffer_time * 1000:
        last_pressed_time = current_time
        global work_index, INTERVAL_SECONDS, NUMBER_OF_WORK1, adjusting_works,select_time_indices
        if setting_mode:
            if adjusting_works:
                NUMBER_OF_WORK1 += 1
                INTERVAL_SECONDS.append(default_interval_seconds)  # Add a default interval for the new work
                select_time_indices.append(0)
                print("Number of works increased to:", NUMBER_OF_WORK1)
            else:
                select_time_indices[work_index] = (select_time_indices[work_index] + 1) % len(select_time)
                time_str = select_time[select_time_indices[work_index]]
                INTERVAL_SECONDS[work_index] = time_to_seconds(time_str)
                print("Interval for work", work_index + 1, "increased to:", time_str)
                
def down_button_handler(pin):
    global last_pressed_time
    
    current_time = utime.ticks_ms()  
    
    if current_time - last_pressed_time > buffer_time * 1000:
        last_pressed_time = current_time
        global work_index, INTERVAL_SECONDS, NUMBER_OF_WORK1, adjusting_works, select_time_indices
        if setting_mode:
            if adjusting_works:
                NUMBER_OF_WORK1 = max(1, NUMBER_OF_WORK1 - 1)
                INTERVAL_SECONDS.pop()
                select_time_indices.pop() # Remove the interval for the last work
                print("Number of works decreased to:", NUMBER_OF_WORK1)
            else:
                select_time_indices[work_index] = (select_time_indices[work_index] - 1) % len(select_time)
                time_str = select_time[select_time_indices[work_index]]
                INTERVAL_SECONDS[work_index] = time_to_seconds(time_str)
                print("Interval for work", work_index + 1, "decreased to:", time_str)
def ok_button_handler(pin):
    global last_pressed_time,last_execution_time, work, interval_seconds, NUMBER_OF_WORK
    
    current_time = utime.ticks_ms()  
    
    if current_time - last_pressed_time > buffer_time * 1000:
        last_pressed_time = current_time
        global setting_mode, work_index, adjusting_works
        if setting_mode:
            if adjusting_works:
                adjusting_works = False
                work_index = 0
                print("Adjusting interval seconds for work", work_index + 1)
            else:
                if work_index < NUMBER_OF_WORK1 - 1:
                    work_index += 1
                    print("Adjusting interval seconds for work", work_index + 1)
                else:
                    setting_mode = False
                    adjusting_works = True
                    work_index = 0
                    print("Setting mode disabled")
                    print("Updated INTERVAL_SECONDS:", INTERVAL_SECONDS)
                    print("Updated NUMBER_OF_WORK:", NUMBER_OF_WORK1)
                    last_execution_time, work, interval_seconds, NUMBER_OF_WORK = load_state()
                    save_state(last_execution_time, work, INTERVAL_SECONDS, NUMBER_OF_WORK1)
                    
                    last_execution_time, work, interval_seconds, NUMBER_OF_WORK = load_state()
                    print(interval_seconds, NUMBER_OF_WORK)
                    
                    #main()
                    
                    
                        
                    

# Function to handle the setting mode
def setting_function(pin):
    global last_pressed_time,setting_mode
    
    current_time = utime.ticks_ms()  
    
    if current_time - last_pressed_time > buffer_time * 1000:
        last_pressed_time = current_time
        global setting_mode
        setting_mode = True
        print("Setting mode enabled")
        if adjusting_works:
            print("Adjusting number of works")
        else:
            print("Adjusting interval seconds for work", work_index + 1)

#manual work function
# Function to enter setting mode
def enter_setting_mode():
    global setting_mode
    setting_mode = True
    print("Entered Setting Mode")
    # Activate the default pin (for example, the first valve)
    pin_list[0].value(1)

# Function to exit setting mode
def exit_setting_mode():
    global setting_mode
    setting_mode = False
    print("Exited Setting Mode")
    # Deactivate all pins except those selected
    for i, valve in enumerate(pin_list):
        valve.value(1 if i in selected_pins else 0)

# Function to handle button presses
def handle_buttons():
    global current_selection, setting_mode

    if not set_button.value():  # If Set button is pressed
        if not setting_mode:
            enter_setting_mode()
        else:
            exit_setting_mode()
        time.sleep(0.2)  # Debounce delay

    if setting_mode:
        if not up_button.value():  # If Up button is pressed
            current_selection = (current_selection + 1) % len(pin_list)
            print(f"Current selection: {current_selection}")
            time.sleep(0.2)  # Debounce delay

        if not down_button.value():  # If Down button is pressed
            current_selection = (current_selection - 1) % len(pin_list)
            print(f"Current selection: {current_selection}")
            time.sleep(0.2)  # Debounce delay

        if not ok_button.value():  # If OK button is pressed
            if current_selection in selected_pins:
                selected_pins.remove(current_selection)
                pin_list[current_selection].value(0)  # Turn off the valve
            else:
                selected_pins.append(current_selection)
                pin_list[current_selection].value(1)  # Turn on the valve
            print(f"Selected pins: {selected_pins}")
            time.sleep(0.2)  # Debounce delay

# Schedule automatic work function
def automatic_work_function(value):
    
    for i, pin in enumerate(pin_list):
        if value == i + 1:
            pin.on()
            
    time.sleep(2)
    
    for i, pin in enumerate(pin_list):
        if value != i + 1:
            pin.off()
                      

    
                        
def main():
    global last_execution_time, work, interval_seconds, NUMBER_OF_WORK
    last_execution_time, work, interval_seconds, NUMBER_OF_WORK = load_state()
    
    while True:
         if automatic_mode:
            # print(last_execution_time, work, interval_seconds, NUMBER_OF_WORK)

            #print("Automatic mode activated")
            manual_mode.off()
            if work>NUMBER_OF_WORK:
                work=NUMBER_OF_WORK
            # Check if work has changed
            global previous_work
            if previous_work is None or work != previous_work:
                automatic_work_function(work)
                previous_work = work
            last_execution_time += 1
            if not setting_mode:
                print_handler("Execution Time:",seconds_to_timer(last_execution_time),"Valve Number:",work)
            save_state(last_execution_time, work, interval_seconds, NUMBER_OF_WORK)
            interval=interval_seconds[work-1]
            if last_execution_time >= interval:
                work = (work % NUMBER_OF_WORK) + 1
                last_execution_time = 0
            time.sleep(1)    
            up_button.irq(trigger=Pin.IRQ_RISING, handler=up_button_handler)
            down_button.irq(trigger=Pin.IRQ_RISING, handler=down_button_handler)
            ok_button.irq(trigger=Pin.IRQ_RISING, handler=ok_button_handler)
            set_button.irq(trigger=Pin.IRQ_RISING, handler=setting_function)
         else:
             up_button.irq(handler=None)
             down_button.irq(handler=None)
             ok_button.irq(handler=None)
             set_button.irq(handler=None)
             print("manual mode")
             manual_mode.on()
             handle_buttons()
             time.sleep(0.1)
         mode_button.irq(trigger=machine.Pin.IRQ_FALLING, handler=toggle_mode)    
         
            

    
    
if __name__ == "__main__":
    #save_state(0, 1,[5,5,5],3)
    
    main()



