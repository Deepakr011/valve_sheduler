
# for esp32
import machine
import time
from machine import Pin,I2C
import ujson as json
import os
import utime
from lcd_api import LcdApi
from i2c_lcd import I2cLcd
import sdcard

#SD card Initialize
# Initialize SPI bus
spi = machine.SPI(2, baudrate=1000000, polarity=0, phase=0, sck=machine.Pin(18), mosi=machine.Pin(23), miso=machine.Pin(19))

# Use GPIO 5 as CS (Chip Select)
cs = machine.Pin(5, machine.Pin.OUT)

# Initialize SD card
sd = sdcard.SDCard(spi, cs)

# Mount the SD card
vfs = os.VfsFat(sd)
os.mount(vfs, "/sd")


# Define the GPIO pins for ESP32
#pins = [1,2,3,4,14,16,17,27,26,25,33,32]
motor_on=Pin(25,Pin.OUT)

pins = [14,27,26]

# Set pins as output
pin_list = [Pin(i, Pin.OUT) for i in pins]

# Setting button pins for ESP32
set_button = Pin(12, Pin.IN, pull=Pin.PULL_UP)
up_button = Pin(13, Pin.IN, pull=Pin.PULL_UP)
down_button = Pin(35, Pin.IN, pull=Pin.PULL_UP)
ok_button = Pin(34, Pin.IN, pull=Pin.PULL_UP)
#set mode button pins
mode_button=Pin(15,Pin.IN,pull=Pin.PULL_UP)


# initial mode
automatic_mode = True
manual_to_automatic=False
# Initialize previous_work variable to keep track of the previous value of work
previous_work = None

#off the job after sertain time
offing_time_end = 2
transition_duration = 0.5# Define desired offing time (in seconds)
last_pin_on_time = 0

#button buffet set
setting_mode =False 
last_pressed_time = 0
buffer_time = 0.5


# Manual state variables
manual_setting_mode = False
current_selection =0
selected_pins = []

# Initial batch size
batch_size = 1

#setting time off
count=0

#display
I2C_ADDR     = 0x27
I2C_NUM_ROWS = 2
I2C_NUM_COLS = 16
try:
    i2c = I2C(0, sda=Pin(21), scl=Pin(22), freq=400000)
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

def load_state(filepath='/sd/store.ini'):
    """
    Load the state from the SD card file. If the file is missing or corrupted, fall back to defaults.
    """
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        return (
            data.get("last_execution_time", 1),
            data.get("work", 1),
            data.get("interval_seconds", [3600, 3600, 3600]),
            data.get("NUMBER_OF_WORK", 3),
            data.get("batch_size", 1),
            data.get("save_water_time_seconds", 3600),
            data.get("skip_valves", []),
        )
    except (OSError, ValueError):
        print("Error loading state. Returning default values.")
        return 1, 1, [3600, 3600, 3600], 3, 1, 3600, []


def save_state(
    last_execution_time, work, interval_seconds, NUMBER_OF_WORK,
    batch_size, save_water_time_seconds, skip_valves, filepath='/sd/store.ini'
):
    """
    Save the state to the SD card file using atomic write and a backup.
    """
    data = {
        "last_execution_time": last_execution_time,
        "work": work,
        "interval_seconds": interval_seconds,
        "NUMBER_OF_WORK": NUMBER_OF_WORK,
        "batch_size": batch_size,
        "save_water_time_seconds": save_water_time_seconds,
        "skip_valves": skip_valves,
    }
    temp_filepath = filepath + ".tmp"
    backup_filepath = filepath + ".bak"
    try:
        # Write data to a temporary file first
        with open(temp_filepath, 'w') as temp_file:
            json.dump(data, temp_file)
            temp_file.flush()  # Flush the file to ensure data is written

        # Backup the existing file
        try:
            if os.stat(filepath):  # Check if the file exists
                os.rename(filepath, backup_filepath)
        except OSError:
            pass  # Ignore if the file doesn't exist

        # Replace the original file with the new file
        os.rename(temp_filepath, filepath)
    except OSError as e:
        print(f"Error saving state: {e}")
        try:
            os.remove(temp_filepath)  # Clean up the temporary file
        except OSError:
            pass  # Ignore errors during cleanup
        
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

def setting_mode_exit():
    global setting_mode,manual_setting_mode,count
    setting_mode=False
    manual_setting_mode=False
    count=0
    reset_variables()
    
# Global variables
current_valves = 1
valve_selection_done = False
setting_time = False
setting_batch = False
setting_save_water = False
setting_skip_valves = False

time_intervals = []
batch_size = 1
save_water_interval = 0
set_skip_valves = [0]

current_time_index = 0
current_batch_size = 1
current_skip_valve = 0    
    
# Initialize/reset variables
def reset_variables():
    global current_valves, valve_selection_done, current_time_index, time_intervals
    global setting_time, batch_size, setting_batch, current_batch_size
    global setting_save_water, save_water_interval
    global setting_skip_valves, set_skip_valves, current_skip_valve
    current_valves = 1  # Default number of valves
    valve_selection_done = False  # Indicates if valve selection is done
    current_time_index = 0  # Default index for time interval selection
    time_intervals = []  # List to store time intervals in seconds
    setting_time = False  # Indicates if the user is setting time intervals
    batch_size = 1  # Default batch size
    setting_batch = False  # Indicates if the user is setting the batch size
    current_batch_size = 1  # Temporary batch size during selection
    setting_save_water = False  # Indicates if the user is setting the save water interval
    save_water_interval = 0  # Save water interval in seconds
    setting_skip_valves = False  # Indicates if the user is setting skip valves
    set_skip_valves = [0]  # List to store skipped valve numbers
    current_skip_valve = 1  # Default skip valve index

# Button handlers
def up_button_handler(pin):
    global current_valves, valve_selection_done, current_time_index, setting_time
    global current_batch_size, setting_batch, setting_save_water
    global current_skip_valve, setting_skip_valves, last_pressed_time
    global last_execution_time, work, interval_seconds, NUMBER_OF_WORK, batch_size_saved, save_water_time_saved,skip_valves
    global setting_mode,set_skip_valves
    
    if not setting_mode:  # Ensure setting_mode is active
        return
    
    current_time = utime.ticks_ms()  
    
    if current_time - last_pressed_time > buffer_time * 1000:
        last_pressed_time = current_time
        if not valve_selection_done:
            current_valves = min(current_valves + 1, len(pins))  # Max limited by available times
            message = ["Valves increased", f"Count: {current_valves}"]
            display_message(lcd, message)
        elif setting_time:  # Adjust time interval index
            current_time_index = min(current_time_index + 1, len(select_time) - 1)
            message = ["Time Interval:", f"Time: {select_time[current_time_index]}"]
            display_message(lcd, message)
        elif setting_batch:  # Adjust batch size
            current_batch_size = min(current_batch_size + 1, current_valves)
            message = ["Batch size set", f"To: {current_batch_size}"]
            display_message(lcd, message)
        elif setting_save_water:  # Adjust save water interval
            current_time_index = min(current_time_index + 1, len(select_time) - 1)
            message = ["Save water intvl:", f"Time: {select_time[current_time_index]}"]
            display_message(lcd, message)

        elif setting_skip_valves:  # Select next valve for skipping
            current_skip_valve = min(current_skip_valve + 1, current_valves+1)
            #print("Select valve to skip:", current_skip_valve)
            if current_skip_valve <=current_valves:
                message = ["Select valve skip", f"Valve: {current_skip_valve}"]
                display_message(lcd, message)
            
            save_skip_valves_save=set_skip_valves
            print(save_skip_valves_save)

            if current_skip_valve > current_valves:
                if all(interval != 0 and len(time_intervals)==current_valves for interval in time_intervals) and current_valves > 0 and batch_size > 0:
                    last_execution_time, work, interval_seconds, NUMBER_OF_WORK, batch_size_saved, save_water_time_saved,skip_valves  = load_state()
                    save_state(last_execution_time, work, time_intervals, current_valves, batch_size, save_water_interval,save_skip_valves_save)
                    
                    last_execution_time, work, interval_seconds, NUMBER_OF_WORK, batch_size_saved, save_water_time_saved,skip_valves  = load_state()
                    automatic_work_function(work, NUMBER_OF_WORK, batch_size_saved,skip_valves)
                    message = [f"Last Exec: {last_execution_time}", f"Work: {work}"]
                    display_message(lcd, message)
                    message2 = [f"Intervals: {time_intervals}", f"Valves: {current_valves}"]
                    display_message(lcd, message2)
                    message3 = [f"Batch: {batch_size}", f"Water Intvl: {save_water_interval}"]
                    display_message(lcd, message3)
                    message4 = [f"Skip Valves: {save_skip_valves_save}", ""]
                    display_message(lcd, message4)

                    
                    
                    print(last_execution_time, work, time_intervals, current_valves, batch_size, save_water_interval,save_skip_valves_save)
                else:
                    message = ["Invalid settings, not saved", "Exited"]
                    display_message(lcd, message)
                
                setting_mode = False
                reset_variables()
                
def down_button_handler(pin):
    global current_valves, valve_selection_done, current_time_index, setting_time
    global current_batch_size, setting_batch, setting_save_water
    global current_skip_valve, setting_skip_valves,last_pressed_time
    
    if not setting_mode:  # Ensure setting_mode is active
        return
    current_time = utime.ticks_ms()  
    
    if current_time - last_pressed_time > buffer_time * 1000:
        last_pressed_time = current_time
        if not valve_selection_done:  # Adjust number of valves
            current_valves = max(current_valves - 1, 1)  # Minimum 1 valve
            #print("Number of valves decreased to:", current_valves)
            message = ["Valves decreased", f"Count: {current_valves}"]
            display_message(lcd, message)

        elif setting_time:  # Adjust time interval index
            current_time_index = max(current_time_index - 1, 0)
            #print(f"Time interval for current valve: {select_time[current_time_index]}")
            message = ["Time intvl (valve)", f"Time: {select_time[current_time_index]}"]
            display_message(lcd, message)

        elif setting_batch:  # Adjust batch size
            current_batch_size = max(current_batch_size - 1, 1)  # Minimum 1 batch
            #print("Batch size decreased to:", current_batch_size)
            message = ["Batch size down", f"To: {current_batch_size}"]
            display_message(lcd, message)

        elif setting_save_water:  # Adjust save water interval
            current_time_index = max(current_time_index - 1, 0)
            #print("Save water interval:", select_time[current_time_index])
            message = ["Save water intvl", f"Time: {select_time[current_time_index]}"]
            display_message(lcd, message)

        elif setting_skip_valves:  # Select previous valve for skipping
            current_skip_valve = max(current_skip_valve - 1, 1)
            #print("Select valve to skip:", current_skip_valve)
            message = ["Select valve skip", f"Valve: {current_skip_valve}"]
            display_message(lcd, message)

            

def ok_button_handler(pin):
    global valve_selection_done, setting_time, time_intervals, current_time_index
    global setting_batch, batch_size, current_batch_size
    global setting_save_water, save_water_interval
    global setting_skip_valves, set_skip_valves, current_skip_valve, last_pressed_time, setting_mode
    
    if not setting_mode:  # Ensure setting_mode is active
        return
    
    current_time = utime.ticks_ms()  
    
    if current_time - last_pressed_time > buffer_time * 1000:
        last_pressed_time = current_time
        if not valve_selection_done:  # Finalize number of valves
            valve_selection_done = True
            message = [f"Valves confirmed:", f"Count: {current_valves}"]
            display_message(lcd, message)
            message2 = ["Setting time", "intervals for each valve"]
            display_message(lcd, message2)
            setting_time = True
        elif setting_time:  # Finalize time interval for the current valve
            if len(time_intervals)==current_valves:
                setting_time = False
                setting_batch = True
                message = [f"Set Batch size", ""]
                display_message(lcd, message)
                
            else:
                selected_time = select_time[current_time_index]
                time_intervals.append(time_to_seconds(selected_time))
                message = [f"Set interval for", f"Valve {len(time_intervals)}: {selected_time}"]
                display_message(lcd, message)

        elif setting_batch:  # Finalize batch size
            batch_size = current_batch_size
            message = ["All time intervals", f"set: {time_intervals}"]
            display_message(lcd, message)
            setting_batch = False
            setting_save_water = True
        elif setting_save_water:  # Finalize save water interval
            save_water_interval = time_to_seconds(select_time[current_time_index])
            message = ["Save water interval", f"confirmed: {select_time[current_time_index]}"]
            display_message(lcd, message)
            setting_save_water = False
            setting_skip_valves = True
        elif setting_skip_valves:  # Toggle skip for the current valve
            if current_skip_valve in set_skip_valves:
                set_skip_valves.remove(current_skip_valve)
                message = [f"Valve {current_skip_valve}", "unmarked for skipping."]
                display_message(lcd, message)
            else:
                set_skip_valves.append(current_skip_valve)
                message = [f"Valve {current_skip_valve}", "marked for skipping."]
                display_message(lcd, message)

            # Exit skip valve setting if done
            if current_skip_valve == current_valves:  # Example condition to exit
                setting_skip_valves = False
                setting_mode = False  # Exit setting mode
                message = ["Skip valve setup", "completed!"]
                display_message(lcd, message)
               
def setting_function(pin):
    global last_pressed_time, setting_mode, NUMBER_OF_WORK1, INTERVAL_SECONDS, select_time_indices, save_water_time_index
    
    current_time = utime.ticks_ms()
    
    if current_time - last_pressed_time > buffer_time * 1000:
        last_pressed_time = current_time
        setting_mode = not setting_mode
        NUMBER_OF_WORK1 = 0
        INTERVAL_SECONDS = []
        select_time_indices = []
        save_water_time_index = 0
        message = ["Setting mode", "Activated"]
        display_message(lcd, message)
        
            
#manual work function
# Function to enter setting mode
def enter_setting_mode():
    global manual_setting_mode,manual_mode_on_valves
    manual_setting_mode = True
    message=["Setting Mode","Activated"]
    display_message(lcd, message)
    # Activate the default pin (for example, the first valve)
    pin_list[0].value(1)
    manual_mode_on_valves=[1]

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
    global current_selection, manual_setting_mode,manual_mode_on_valves

    if not set_button.value():  # If Set button is pressed
        if not manual_setting_mode:
            enter_setting_mode()
        else:
            exit_setting_mode()
        time.sleep(0.2)  # Debounce delay

    if manual_setting_mode:
        if not up_button.value():  # If Up button is pressed
            current_selection = (current_selection+1) % len(pin_list)
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
                print(current_selection)
                selected_pins.remove(current_selection)
                pin_list[current_selection].value(0)  # Turn off the valve
            else:
                selected_pins.append(current_selection)
                pin_list[current_selection].value(1)
            selected_pinlist=[x+1 for x in selected_pins]
            message =["selected pins",f"Pins:{selected_pinlist}"]
            manual_mode_on_valves=selected_pinlist
            display_message(lcd, message)
            time.sleep(0.2)  # Debounce delay
# Schedule automatic work function
def automatic_work_function(valve, number_of_work, batch_size, skip_valves):
    global on_valves,current_valve
    
    # Filter out skipped valves from the list of pin indices
    available_indices = [i for i in range(number_of_work) if i + 1 not in skip_valves]
    
    if not available_indices:
        for pins in pin_list:
            pins.on()
        return

    if batch_size == 1:
        for i, pin in enumerate(pin_list):
            if valve == i + 1:
                pin.on()
                on_valves = [valve]
        current_valve=valve
        
        time.sleep(2)
        
        for i, pin in enumerate(pin_list):
            if valve != i + 1:
                pin.off()
                
    else:
        # Ensure batch size does not exceed available valves
        batch_size = min(batch_size, len(available_indices))
        
        # Calculate the start index within the available indices
        start_index = (valve * batch_size) % len(available_indices)
        
        # Select the batch of valves to turn on
        on_pins = []
        for i in range(batch_size):
            pin_index = available_indices[(start_index + i) % len(available_indices)]
            # Turn on the valve
            pin_list[pin_index].on()
            on_pins.append(pin_index)
        current_valve=[x + 1 for x in on_pins]
        
        time.sleep(2)  # Simulate work
        
        # Turn off all other valves not in the batch
        for i, pin in enumerate(pin_list):
            if i not in on_pins:
                pin.off()       
        on_valves = [x + 1 for x in on_pins]

# Main Task
def main():
 
    global exit_rest_mode,setting_mode
    global last_execution_time, work, interval_seconds, NUMBER_OF_WORK, batch_size_saved, manual_to_automatic, count, rest_time,save_water_time_saved,current_mode,current_valve,skip_valves
    last_execution_time, work, interval_seconds, NUMBER_OF_WORK, batch_size_saved, save_water_time_saved,skip_valves = load_state()
    rest_time = 0
    previous_work = None
    save_old_data=0

    while True:
        exit_rest_mode=False
        save_old_data +=1
        if automatic_mode:
            current_mode="automatic"

            if manual_to_automatic:
                automatic_work_function(work, NUMBER_OF_WORK, batch_size_saved,skip_valves)
                manual_to_automatic = False

            if work > NUMBER_OF_WORK:
                work = NUMBER_OF_WORK

            if previous_work is None or work != previous_work:
                print(work, NUMBER_OF_WORK)
                while work in skip_valves and NUMBER_OF_WORK:
                    work += 1
                    last_execution_time = 0
                
                automatic_work_function(work, NUMBER_OF_WORK, batch_size_saved,skip_valves)
                previous_work = work

            last_execution_time += 1
            if not setting_mode:
                message = [f"Auto,{seconds_to_timer(last_execution_time)}", f"V:{current_valve},B:{batch_size_saved}"]
                display_message(lcd, message)
                setting_mode_exit()

            if setting_mode or manual_setting_mode:
                count += 1
                if count >= 300:
                    setting_mode_exit()
            #save_state(last_execution_time, work, interval_seconds, NUMBER_OF_WORK, batch_size_saved, save_water_time_saved,skip_valves)
            #save data in every minute 
            if save_old_data==60:
                save_state(last_execution_time, work, interval_seconds, NUMBER_OF_WORK, batch_size_saved, save_water_time_saved,skip_valves)
                save_old_data=0
            interval = interval_seconds[work - 1]
            
            if last_execution_time >= interval:
                work += 1
                last_execution_time = 0
                while work in skip_valves:
                    print(f"Skipping valve {work} as per configuration")
                    work += 1
                    if work > NUMBER_OF_WORK:
                        work = 1
                        rest_time = 0
                        
                        # Enter rest period
                        while rest_time < save_water_time_saved:
                            global current_mode
                            global exit_rest_mode
                            current_mode="rest"
                            message = ["Rest mode", f"{seconds_to_timer(rest_time)}"]
                            display_message(lcd, message)
                            rest_time += 1
                            motor_on.off()
                            time.sleep(1)
                            print(exit_rest_mode)
                            print("sikp loop")
                            if exit_rest_mode:
                                print(exit_rest_mode)
                                print("exit")
                                break
                            save_state(last_execution_time, work, interval_seconds, NUMBER_OF_WORK, batch_size_saved, save_water_time_saved,skip_valves)
                            if save_old_data==60:
                                save_state(last_execution_time, work, interval_seconds, NUMBER_OF_WORK, batch_size_saved, save_water_time_saved,skip_valves)
                                save_old_data=0
                            save_old_data +=1
                if work > NUMBER_OF_WORK:
                    work = 1
                    rest_time = 0
                    
                    # Enter rest period
                    while rest_time < save_water_time_saved:
                        global current_mode
                        global exit_rest_mode
                        current_mode="rest"
                        message = ["Rest mode", f"{seconds_to_timer(rest_time)}"]
                        display_message(lcd, message)
                        if exit_rest_mode:
                            print("Exiting rest mode...")
                            break
                        rest_time += 1
                        motor_on.off()
                        time.sleep(1)
                        print(exit_rest_mode)
                        print("main loop")
                        #save_state(last_execution_time, work, interval_seconds, NUMBER_OF_WORK, batch_size_saved, save_water_time_saved,skip_valves)
                        # save the data every minute
                        if save_old_data==60:
                            save_state(last_execution_time, work, interval_seconds, NUMBER_OF_WORK, batch_size_saved, save_water_time_saved,skip_valves)
                            save_old_data=0
                        save_old_data +=1  
                        set_button.irq(trigger=Pin.IRQ_RISING, handler=setting_function)
                        mode_button.irq(trigger=Pin.IRQ_RISING, handler=toggle_mode)
                        if setting_mode or not automatic_mode:
                            break

            time.sleep(1)
            motor_on.on()
            up_button.irq(trigger=Pin.IRQ_RISING, handler=up_button_handler)
            down_button.irq(trigger=Pin.IRQ_FALLING, handler=down_button_handler)
            ok_button.irq(trigger=Pin.IRQ_FALLING, handler=ok_button_handler)
            set_button.irq(trigger=Pin.IRQ_RISING, handler=setting_function)
        else:
            current_mode ="manual"
            setting_mode=False
            up_button.irq(handler=None)
            down_button.irq(handler=None)
            ok_button.irq(handler=None)
            set_button.irq(handler=None)
            if not manual_setting_mode:    
                message = ["manual mode", "Activated"]
                display_message(lcd, message)
                motor_on.on()
            else:
                motor_on.off()
            handle_buttons()
            time.sleep(0.2)

        mode_button.irq(trigger=machine.Pin.IRQ_FALLING, handler=toggle_mode)


if __name__ == "__main__":
    main()

        
