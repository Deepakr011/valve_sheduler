import time
from machine import Pin,I2C
import ujson as json
import os
import utime
from lcd_api import LcdApi
from i2c_lcd import I2cLcd

manual_mode=Pin("LED",Pin.OUT)
# Pin configuration from Pin 0 to 7
pins=[0,1,2,3,4,5,6,7]
pin_list = [Pin(i, Pin.OUT) for i in pins]
#setting button pins 
set_button=Pin(10,Pin.IN,pull=Pin.PULL_UP)
up_button=Pin(11,Pin.IN,pull=Pin.PULL_UP)
down_button=Pin(12,Pin.IN,pull=Pin.PULL_UP)
ok_button=Pin(13,Pin.IN,pull=Pin.PULL_UP)

#set mode button pins
mode_button=Pin(15,Pin.IN,pull=Pin.PULL_UP)

# initial mode
automatic_mode = True
manual_to_automatic=False
# Initialize previous_work variable to keep track of the previous value of work
previous_work = None


#button veriables
setting_mode = False
adjusting_works = True
adjusting_batch_size = False

#off the job after sertain time
offing_time_end = 2
transition_duration = 0.5# Define desired offing time (in seconds)
last_pin_on_time = 0

# Constants
default_interval_seconds =0
NUMBER_OF_WORK1 = 0
INTERVAL_SECONDS = [default_interval_seconds] * NUMBER_OF_WORK1
select_time_indices = [0] * NUMBER_OF_WORK1
work_index = 0

#button buffet set
setting_mode =False 
last_pressed_time = 0
buffer_time = 0.5

# Manual state variables
manual_setting_mode = False
current_selection = 0
selected_pins = []

# Initial batch size
batch_size = 1

#display
I2C_ADDR     = 0x27
I2C_NUM_ROWS = 2
I2C_NUM_COLS = 16
try:
    i2c = I2C(0, sda=Pin(16), scl=Pin(17), freq=400000)
    lcd = I2cLcd(i2c, I2C_ADDR, I2C_NUM_ROWS, I2C_NUM_COLS)
except Exception as e:
    print(f"Failed to initialize I2C or LCD: {e}")
    lcd = None

#setting the time
select_time = ["0:01","0:02","0:05", "0:10", "0:15", "0:30", "0:45", "1:00", "1:15", "1:30", "1:45", "2:00", 
               "2:15", "2:30", "2:45", "3:00", "3:15", "3:30", "3:45", "4:00", "4:15", "4:30", 
               "4:45", "5:00", "5:15", "5:30", "5:45", "6:00", "6:15", "6:30", "6:45", "7:00", 
               "7:15", "7:30", "7:45", "8:00", "8:15", "8:30", "8:45", "9:00", "9:15", "9:30", 
               "9:45", "10:00", "10:15", "10:30", "10:45", "11:00", "11:15", "11:30", "11:45", 
               "12:00"]
#display function
def display_message(lcd, messages):
    
    if lcd is not None:
        try:
            lcd.clear()
            for row, message in enumerate(messages):
                lcd.move_to(0, row)
                lcd.putstr(message)
        except Exception as e:
            print(f"Failed to display messages on LCD: {e}")
            for row, message in enumerate(messages):
                print(f"Message: {message} (Row: {row}, Col: 0)")
    else:
        for row, message in enumerate(messages):
            print(f"Message: {message} (Row: {row}, Col: 0)")

def toggle_mode(pin):
    global last_pressed_time
    current_time = utime.ticks_ms()  
    
    if current_time - last_pressed_time > buffer_time * 1000:
        last_pressed_time = current_time
        global automatic_mode,manual_to_automatic
        automatic_mode = not automatic_mode
        if automatic_mode:
            manual_to_automatic = True


def load_state():
    try:
        with open('/store.ini', 'r') as f:
            data = json.load(f)
            last_execution_time = data["last_execution_time"]
            work = data["work"]
            interval_seconds = data["interval_seconds"]
            NUMBER_OF_WORK = data["NUMBER_OF_WORK"]
            batch_size=data["batch_size"]
            return last_execution_time, work, interval_seconds, NUMBER_OF_WORK,batch_size
    except (OSError, ValueError, IndexError):
        print("Error loading state.")
        return None, None, [], 0,1

def save_state(last_execution_time, work, interval_seconds, NUMBER_OF_WORK,batch_size):
    data = {
        "last_execution_time": last_execution_time,
        "work": work,
        "interval_seconds": interval_seconds,
        "NUMBER_OF_WORK": NUMBER_OF_WORK,
        "batch_size":batch_size
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
def reset_interval_seconds():
    global INTERVAL_SECONDS, select_time_indices, NUMBER_OF_WORK1
    INTERVAL_SECONDS = [default_interval_seconds] * NUMBER_OF_WORK1
    select_time_indices = [0] * NUMBER_OF_WORK1
    
def up_button_handler(pin):
    global last_pressed_time, work_index, INTERVAL_SECONDS, NUMBER_OF_WORK1, adjusting_works, select_time_indices, batch_size
    
    current_time = utime.ticks_ms()  
    
    if current_time - last_pressed_time > buffer_time * 1000:
        last_pressed_time = current_time
        if setting_mode:
            if adjusting_batch_size:
                batch_size += 1
                if batch_size > NUMBER_OF_WORK1:  # Ensure batch size doesn't exceed the number of works
                    batch_size = 1
                message =["Adj Batch Size",f"Batch incr to: {batch_size}"]
                display_message(lcd, message)
            else:
                if adjusting_works:
                    NUMBER_OF_WORK1 += 1
                    if NUMBER_OF_WORK1 > len(pin_list):
                        NUMBER_OF_WORK1=1
                    INTERVAL_SECONDS.append(default_interval_seconds)  # Add a default interval for the new work
                    select_time_indices.append(0)
                    message = ["Adj #Valves",f"Valve incr to: {NUMBER_OF_WORK1}"]
                    display_message(lcd, message)
                else:
                    select_time_indices[work_index] = (select_time_indices[work_index] + 1) % len(select_time)
                    time_str = select_time[select_time_indices[work_index]]
                    INTERVAL_SECONDS[work_index] = time_to_seconds(time_str)
                    message = [f"V{work_index+1}",f"Intv incr: {time_str}"]
                    display_message(lcd, message)

def down_button_handler(pin):
    global last_pressed_time, work_index, INTERVAL_SECONDS, NUMBER_OF_WORK1, adjusting_works, select_time_indices, batch_size
    
    current_time = utime.ticks_ms()  
    
    if current_time - last_pressed_time > buffer_time * 1000:
        last_pressed_time = current_time
        if setting_mode:
            if adjusting_batch_size:
                batch_size -= 1
                if batch_size < 1:  # Ensure batch size doesn't go below 1
                    batch_size = NUMBER_OF_WORK1
                message = ["Adj Batch Size",f"Batch decr to: {batch_size}"]
                display_message(lcd, message)
            else:
                if adjusting_works:
                    NUMBER_OF_WORK1 = max(1, NUMBER_OF_WORK1 - 1)
                    INTERVAL_SECONDS.pop()
                    select_time_indices.pop()  # Remove the interval for the last work
                    message = ["Adj #Valves",f"Valve decr to:{NUMBER_OF_WORK1}"]
                    display_message(lcd, message)
                else:
                    select_time_indices[work_index] = (select_time_indices[work_index] - 1) % len(select_time)
                    time_str = select_time[select_time_indices[work_index]]
                    INTERVAL_SECONDS[work_index] = time_to_seconds(time_str)
                    message = [f"V{work_index+1}",f"Intv decr: {time_str}"] 
                    display_message(lcd, message)
                    
def ok_button_handler(pin):
    global last_pressed_time, last_execution_time, work, interval_seconds, NUMBER_OF_WORK,batch_size_saved
    
    current_time = utime.ticks_ms()  
    
    if current_time - last_pressed_time > buffer_time * 1000:
        last_pressed_time = current_time
        global setting_mode, work_index, adjusting_works, adjusting_batch_size
        if setting_mode:
            if adjusting_works:
                adjusting_works = False
                work_index = 0
                message = [f"V{work_index+1}",f"Adj Intv:V{work_index+1}"]
                display_message(lcd, message)
            elif not adjusting_batch_size:
                if work_index < NUMBER_OF_WORK1 - 1:
                    work_index += 1
                    message = [f"V{work_index+1}",f"Adj Intv:V{work_index+1}"]
                    display_message(lcd, message)

                else:
                    adjusting_batch_size = True
                    message = ["set batch","Adj Batch Size",]
                    display_message(lcd, message)
                    
            else:
                setting_mode = False
                adjusting_works = True
                adjusting_batch_size = False
                work_index = 0
                message =["Setting end",f"{INTERVAL_SECONDS},{NUMBER_OF_WORK1},{batch_size}"]
                display_message(lcd, message)
                print(message)
                
                # Validate settings before saving
                if all(interval > 0 for interval in INTERVAL_SECONDS) and NUMBER_OF_WORK1 > 0 and batch_size > 0:
                    last_execution_time, work, interval_seconds, NUMBER_OF_WORK, batch_size_saved = load_state()
                    save_state(last_execution_time, work, INTERVAL_SECONDS, NUMBER_OF_WORK1, batch_size)
                    
                    last_execution_time, work, interval_seconds, NUMBER_OF_WORK, batch_size_saved = load_state()
                    automatic_work_function(work, NUMBER_OF_WORK, batch_size_saved)
                else:
                    message = ["Invalid settings, not saved","Exited"]
                    display_message(lcd, message)
                # Reset INTERVAL_SECONDS
                reset_interval_seconds()    
                    
# Function to handle the setting mode
def setting_function(pin):
    global last_pressed_time,setting_mode, NUMBER_OF_WORK1, INTERVAL_SECONDS, select_time_indices
    
    current_time = utime.ticks_ms()  
    
    if current_time - last_pressed_time > buffer_time * 1000:
        last_pressed_time = current_time
        global setting_mode
        setting_mode = True
        NUMBER_OF_WORK1 = 0
        INTERVAL_SECONDS = []
        select_time_indices = []
        message=["Setting mode","Activated"]
        display_message(lcd, message)
        
            
#manual work function
# Function to enter setting mode
def enter_setting_mode():
    global manual_setting_mode
    manual_setting_mode = True
    message=["Setting Mode","Activated"]
    display_message(lcd, message)
    # Activate the default pin (for example, the first valve)
    pin_list[0].value(1)

# Function to exit setting mode
def exit_setting_mode():
    global manual_setting_mode
    manual_setting_mode = False
    message=["Setting Mode","Exited"]
    display_message(lcd, message)
    # Deactivate all pins except those selected
    for i, valve in enumerate(pin_list):
        valve.value(1 if i in selected_pins else 0)

# Function to handle button presses
def handle_buttons():
    global current_selection, manual_setting_mode

    if not set_button.value():  # If Set button is pressed
        if not manual_setting_mode:
            enter_setting_mode()
        else:
            exit_setting_mode()
        time.sleep(0.2)  # Debounce delay

    if manual_setting_mode:
        if not up_button.value():  # If Up button is pressed
            current_selection = (current_selection + 1) % len(pin_list)
            message=["select valves",f"valve:{current_selection+1}"]
            display_message(lcd, message)
            time.sleep(0.2)  # Debounce delay

        if not down_button.value():  # If Down button is pressed
            current_selection = (current_selection - 1) % len(pin_list)
            message = ["select valves",f"valve:{current_selection+1}"]
            display_message(lcd, message)
            time.sleep(0.2)  # Debounce delay

        if not ok_button.value():  # If OK button is pressed
            if current_selection in selected_pins:
                selected_pins.remove(current_selection)
                pin_list[current_selection].value(0)  # Turn off the valve
            else:
                selected_pins.append(current_selection)
                pin_list[current_selection].value(1)# Turn on the valve    
            message =["selected pins",f"Pins:{selected_pins}"]
            display_message(lcd, message)
            time.sleep(0.2)  # Debounce delay

# Schedule automatic work function
def automatic_work_function(value, number_of_work, batch_size):
    if batch_size==1:
        for i, pin in enumerate(pin_list):
            if value == i + 1:
                pin.on()
            
        time.sleep(2)
    
        for i, pin in enumerate(pin_list):
            if value != i + 1:
                pin.off()
    else:
        # Ensure batch size is not greater than the total number of pins
        batch_size = min(batch_size, number_of_work)

        # Calculate the start index ensuring it wraps within the number_of_work
        start_index = (value * batch_size) % number_of_work
    
        # Turn on the batch of pins
        on_pins = []
        for i in range(batch_size):
            pin_index = (start_index + i) % number_of_work
            #print(f"on pin {pin_list[pin_index]}")
            pin_list[pin_index].on() 
            on_pins.append(pin_index)
    
        time.sleep(2)  # Simulate work
    
        # Turn off the pins that are not in the batch
        for i, pin in enumerate(pin_list):
            if i not in on_pins:
                #print(f"off pin {pin}")
                pin.off()
    
                        
def main():
    global last_execution_time, work, interval_seconds, NUMBER_OF_WORK,batch_size_saved,manual_to_automatic
    last_execution_time, work, interval_seconds, NUMBER_OF_WORK,batch_size_saved = load_state()
    while True:
        if automatic_mode:
            manual_mode.off()
            # Call automatic_work_function once after transitioning from manual to automatic
            if manual_to_automatic:
                automatic_work_function(work, NUMBER_OF_WORK, batch_size_saved)
                manual_to_automatic = False
            if work>NUMBER_OF_WORK:
                work=NUMBER_OF_WORK
            # Check if work has changed
            global previous_work
            if previous_work is None or work != previous_work:
                print(work,NUMBER_OF_WORK)
                automatic_work_function(work,NUMBER_OF_WORK,batch_size_saved)
                previous_work = work
            last_execution_time += 1
            if not setting_mode:
                message=["Automatic mode",f"{seconds_to_timer(last_execution_time)},V:{work},B:{batch_size_saved}"]
                display_message(lcd, message)
            save_state(last_execution_time, work, interval_seconds, NUMBER_OF_WORK,batch_size_saved)
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
            manual_mode.on()
            up_button.irq(handler=None)
            down_button.irq(handler=None)
            ok_button.irq(handler=None)
            set_button.irq(handler=None)
            if not manual_setting_mode:
                message=["manual mode","Activated"]
                display_message(lcd,message)
            handle_buttons()
            time.sleep(0.1)
        mode_button.irq(trigger=machine.Pin.IRQ_FALLING, handler=toggle_mode)    
         
            

    
    
if __name__ == "__main__":
    main()




