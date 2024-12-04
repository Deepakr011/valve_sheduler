
# for esp32
import machine
import time
from machine import Pin,I2C
import ujson as json
import os
import utime
from lcd_api import LcdApi
from i2c_lcd import I2cLcd

#MQTT
import uasyncio as asyncio
from umqtt.robust import MQTTClient
import network
import ujson

# Wi-Fi Configuration
SSID = 'OPPO A53'
PASSWORD = 'deepu123456'

# MQTT Configuration
MQTT_BROKER = "mqtt.eclipseprojects.io"
MQTT_CLIENT_ID = "deepak_" + str(machine.unique_id())
MQTT_TOPIC_SUB = "deepak/sub"
MQTT_TOPIC_PUB = "deepak/pub"

# device-specific variables
DEVICE_ID = "ESP32-S3-001"  # Replace with your actual device ID


manual_mode = Pin(2, Pin.OUT)

# Define the GPIO pins for ESP32
pins = [14, 27, 26, 25, 33, 32, 13, 12]

# Set pins as output
pin_list = [Pin(i, Pin.OUT) for i in pins]

# Setting button pins for ESP32
set_button = Pin(12, Pin.IN, pull=Pin.PULL_UP)
up_button = Pin(13, Pin.IN, pull=Pin.PULL_UP)
down_button = Pin(14, Pin.IN, pull=Pin.PULL_UP)
ok_button = Pin(27, Pin.IN, pull=Pin.PULL_UP)

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


def load_state():
    try:
        with open('/store.ini', 'r') as f:
            data = json.load(f)
            last_execution_time = data["last_execution_time"]
            work = data["work"]
            interval_seconds = data["interval_seconds"]
            NUMBER_OF_WORK = data["NUMBER_OF_WORK"]
            batch_size = data["batch_size"]
            save_water_time_seconds = data["save_water_time_seconds"]
            return last_execution_time, work, interval_seconds, NUMBER_OF_WORK, batch_size, save_water_time_seconds
    except (OSError, ValueError, IndexError):
        print("Error loading state.")
        return 1, 1, [3600,3600,3600], 3, 1, 3600

def save_state(last_execution_time, work, interval_seconds, NUMBER_OF_WORK, batch_size, save_water_time_seconds):
    data = {
        "last_execution_time": last_execution_time,
        "work": work,
        "interval_seconds": interval_seconds,
        "NUMBER_OF_WORK": NUMBER_OF_WORK,
        "batch_size": batch_size,
        "save_water_time_seconds": save_water_time_seconds
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

def setting_mode_exit():
    global setting_mode,manual_setting_mode,count
    setting_mode=False
    manual_setting_mode=False
    count=0
    
# Additional global variables
save_water_time_index = 0
adjusting_save_water = False
# Declare global variables
adjusting_skip_valves = False  # New flag for skipping valves
skip_valves =0 # Variable to hold the number of valves to skip


def up_button_handler(pin):
    global last_pressed_time, work_index, INTERVAL_SECONDS, NUMBER_OF_WORK1, adjusting_works, select_time_indices, batch_size, save_water_time_index, adjusting_save_water, adjusting_skip_valves, skip_valves
    
    current_time = utime.ticks_ms()  
    
    if current_time - last_pressed_time > buffer_time * 1000:
        last_pressed_time = current_time
        if setting_mode:
            if adjusting_batch_size:
                batch_size += 1
                if batch_size > NUMBER_OF_WORK1:  # Ensure batch size doesn't exceed the number of works
                    batch_size = 1
                message = ["Adj Batch Size", f"Batch incr to: {batch_size}"]
                display_message(lcd, message)
            elif adjusting_save_water:
                save_water_time_index = (save_water_time_index + 1) % len(select_time)
                save_water_time_str = select_time[save_water_time_index]
                message = ["Adj Save Water", f"Save incr: {save_water_time_str}"]
                display_message(lcd, message)
            elif adjusting_skip_valves:
                skip_valves += 1
                if skip_valves > NUMBER_OF_WORK1:  # Ensure skip valves don't exceed the number of works
                    skip_valves = 0  # Reset to 0 if it exceeds
                message = ["Adj Skip Valves", f"Skip incr to: {skip_valves}"]
                display_message(lcd, message)
            else:
                if adjusting_works:
                    NUMBER_OF_WORK1 += 1
                    if NUMBER_OF_WORK1 > len(pin_list):
                        NUMBER_OF_WORK1 = 1
                    INTERVAL_SECONDS.append(default_interval_seconds)  # Add a default interval for the new work
                    select_time_indices.append(0)
                    message = ["Adj #Valves", f"Valve incr to: {NUMBER_OF_WORK1}"]
                    display_message(lcd, message)
                else:
                    if work_index < len(select_time_indices):
                        select_time_indices[work_index] = (select_time_indices[work_index] + 1) % len(select_time)
                        time_str = select_time[select_time_indices[work_index]]
                        INTERVAL_SECONDS[work_index] = time_to_seconds(time_str)
                        message = [f"V{work_index+1}", f"Intv incr: {time_str}"]
                        display_message(lcd, message)


def down_button_handler(pin):
    global last_pressed_time, work_index, INTERVAL_SECONDS, NUMBER_OF_WORK1, adjusting_works, select_time_indices, batch_size, save_water_time_index, adjusting_save_water, adjusting_skip_valves, skip_valves
    
    current_time = utime.ticks_ms()  
    
    if current_time - last_pressed_time > buffer_time * 1000:
        last_pressed_time = current_time
        if setting_mode:
            if adjusting_batch_size:
                batch_size -= 1
                if batch_size < 1:  # Ensure batch size doesn't go below 1
                    batch_size = NUMBER_OF_WORK1
                message = ["Adj Batch Size", f"Batch decr to: {batch_size}"]
                display_message(lcd, message)
            elif adjusting_save_water:
                save_water_time_index = (save_water_time_index - 1) % len(select_time)
                save_water_time_str = select_time[save_water_time_index]
                message = ["Adj Save Water", f"Save decr: {save_water_time_str}"]
                display_message(lcd, message)
            elif adjusting_skip_valves:
                skip_valves -= 1
                if skip_valves < 0:  # Ensure skip valves don't go below 0
                    skip_valves = NUMBER_OF_WORK1
                message = ["Adj Skip Valves", f"Skip decr to: {skip_valves}"]
                display_message(lcd, message)
            else:
                if adjusting_works:
                    NUMBER_OF_WORK1 = max(1, NUMBER_OF_WORK1 - 1)
                    if INTERVAL_SECONDS:
                        INTERVAL_SECONDS.pop()
                    else:
                        INTERVAL_SECONDS = [1]  # Default to 1 if empty
                    if select_time_indices:
                        select_time_indices.pop()
                    else:
                        select_time_indices = [0]  # Default to 0 if empty
                    message = ["Adj #Valves", f"Valve decr to: {NUMBER_OF_WORK1}"]
                    display_message(lcd, message)
                else:
                    if work_index < len(select_time_indices):
                        select_time_indices[work_index] = (select_time_indices[work_index] - 1) % len(select_time)
                        time_str = select_time[select_time_indices[work_index]]
                        INTERVAL_SECONDS[work_index] = time_to_seconds(time_str)
                        message = [f"V{work_index+1}", f"Intv decr: {time_str}"]
                        display_message(lcd, message)

# Update ok_button_handler function
def ok_button_handler(pin):
    global last_pressed_time, last_execution_time, work, interval_seconds, NUMBER_OF_WORK, batch_size_saved, save_water_time_index, adjusting_save_water, adjusting_skip_valves, skip_valves
    
    current_time = utime.ticks_ms()  
    
    if current_time - last_pressed_time > buffer_time * 1000:
        last_pressed_time = current_time
        global setting_mode, work_index, adjusting_works, adjusting_batch_size
        if setting_mode:
            if adjusting_works:
                adjusting_works = False
                work_index = 0
                message = [f"V{work_index+1}", f"Adj Intv:V{work_index+1}"]
                display_message(lcd, message)
            elif not adjusting_batch_size and not adjusting_save_water and not adjusting_skip_valves:
                if work_index < NUMBER_OF_WORK1 - 1:
                    work_index += 1
                    message = [f"V{work_index+1}", f"Adj Intv:V{work_index+1}"]
                    display_message(lcd, message)
                else:
                    adjusting_batch_size = True
                    message = ["set batch", "Adj Batch Size"]
                    display_message(lcd, message)
            elif adjusting_batch_size:
                adjusting_batch_size = False
                adjusting_save_water = True
                message = ["set save water", "Adj Save Water"]
                display_message(lcd, message)
            elif adjusting_save_water:
                adjusting_save_water = False
                adjusting_skip_valves = True
                message = ["set skip valves", "Adj Skip Valves"]
                display_message(lcd, message)
            elif adjusting_skip_valves:
                setting_mode = False
                adjusting_works = True
                adjusting_batch_size = False
                adjusting_skip_valves = False
                work_index = 0
                save_water_time_str = select_time[save_water_time_index]
                save_water_time_seconds = time_to_seconds(save_water_time_str)
                print(save_water_time_seconds)
                message = ["Setting end", f"{INTERVAL_SECONDS},{NUMBER_OF_WORK1},{batch_size},{save_water_time_str},{skip_valves}"]
                display_message(lcd, message)
                print(message)
                
                if all(interval != 0 for interval in INTERVAL_SECONDS) and NUMBER_OF_WORK1 > 0 and batch_size > 0 and save_water_time_seconds > 0:
                    last_execution_time, work, interval_seconds, NUMBER_OF_WORK, batch_size_saved, save_water_time_saved = load_state()
                    save_state(last_execution_time, work, INTERVAL_SECONDS, NUMBER_OF_WORK1, batch_size, save_water_time_seconds, skip_valves)
                    
                    last_execution_time, work, interval_seconds, NUMBER_OF_WORK, batch_size_saved, save_water_time_saved = load_state()
                    automatic_work_function(work, NUMBER_OF_WORK, batch_size_saved)
                else:
                    message = ["Invalid settings, not saved", "Exited"]
                    display_message(lcd, message)
                reset_interval_seconds()
                
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

    #if not set_button.value():
    if  set_button.value():# If Set button is pressed
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
def automatic_work_function(valve, number_of_work, batch_size):
    global on_valves
    
    if batch_size==1:
        for i, pin in enumerate(pin_list):
            if valve == i + 1:
                pin.on()
                on_valves=[valve]
            
        time.sleep(2)
    
        for i, pin in enumerate(pin_list):
            if valve != i + 1:
                pin.off()
    else:
        # Ensure batch size is not greater than the total number of pins
        batch_size = min(batch_size, number_of_work)

        # Calculate the start index ensuring it wraps within the number_of_work
        start_index = (valve * batch_size) % number_of_work
    
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
        on_valves=[x+1 for x in on_pins]
# Network Task
async def network_task():
    global on_valves,interval_seconds,NUMBER_OF_WORK,current_mode,manual_mode_on_valves,exit_rest_mode
    wlan = network.WLAN(network.STA_IF)
    
    async def connect_wifi():
        try:
            if not wlan.active():
                print("Activating WiFi interface...")
                wlan.active(True)
                await asyncio.sleep(1)  # Small delay to ensure activation
                
            if not wlan.isconnected():
                print("Attempting to connect to WiFi...")
                wlan.connect(SSID, PASSWORD)
                
                for _ in range(10):  # Wait up to 10 seconds for connection
                    if wlan.isconnected():
                        print("WiFi Connected:", wlan.ifconfig())
                        return True
                    await asyncio.sleep(1)
                
                print("Failed to connect to WiFi")
                return False
            else:
                print("WiFi already connected:", wlan.ifconfig())
                return True
            
        except OSError as e:
            print(f"OSError during WiFi connection: {e}")
            print("Resetting WiFi interface...")
            wlan.active(False)
            await asyncio.sleep(2)
            wlan.active(True)
            return False

    async def maintain_connection():
        retries = 0
        max_retries = 5
        
        while True:
            if not wlan.isconnected():
                print("WiFi connection lost. Reconnecting...")
                
                while not wlan.isconnected() and retries < max_retries:
                    success = await connect_wifi()
                    if success:
                        retries = 0  # Reset retries after a successful connection
                        break
                    retries += 1
                    delay = min(2 ** retries, 30)  # Exponential backoff
                    print(f"Reconnect attempt {retries} failed. Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                
                if retries >= max_retries:
                    print("Exceeded maximum retry attempts. Resetting WiFi interface...")
                    wlan.active(False)
                    await asyncio.sleep(2)
                    wlan.active(True)
                    retries = 0
            
            await asyncio.sleep(5)  # Check every 5 seconds

    async def mqtt_task():
        global on_valves,NUMBER_OF_WORK,interval_seconds,exit_rest_mode
        def process_mqtt_data(message):
            global automatic_mode,manual_mode_on_valves,manual_to_automatic,current_mode,exit_rest_mode
            if "valve" in message and "hours" in message or "minutes" in message or "seconds" in message:
                valve = message["valve"]
                hours = message.get("hours", 0)
                minutes = message.get("minutes", 0)
                seconds = message.get("seconds", 0)
                total_seconds = hours * 3600 + minutes * 60 + seconds
            if "mode" in message:
                mode=message["mode"]
                if mode=="automatic":
                    exit_rest_mode=True
                    print(exit_rest_mode)
                    print("ok")
                    
            if "on_valves" in message and "manual_mode" in message:
                manual_on_valves = message["on_valves"]
                on_manual_valves = message["manual_mode"]
                if on_manual_valves:
                    automatic_mode = False
                    manual_to_automatic=True
                    current_mode="manual"
                    for index in selected_pins:
                        
                        pin_list[index].value(1)
                        
                    time.sleep(2)
                    
                    for index, pin in enumerate(pin_list):
                        if index not in selected_pins:
                            pin.value(0)
                    manual_mode_on_valves=manual_on_valves       
                else:
                    automatic_mode = True
                    manual_to_automatic=False
                    current_mode="automatic"
            if "rest_hours" in message and "rest_minutes" in message:
                print("restmode")
        client = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER)
        await asyncio.sleep(1)
        def mqtt_callback(topic, msg):
            print(f"Received message on topic {topic.decode()}: {msg.decode()}")
            try:
                message = json.loads(msg.decode())
                process_mqtt_data(message)
            except Exception as e:
                print(f"Failed to decode JSON message: {e}")
        
        publish_interval = 1 # seconds

        while True:
            if wlan.isconnected():
                try:
                    print("Connecting to MQTT broker...")
                    client.set_callback(mqtt_callback)
                    client.connect()
                    print("MQTT Connected")
                    
                    client.subscribe(MQTT_TOPIC_SUB)
                    print(f"Subscribed to topic: {MQTT_TOPIC_SUB}")
                    
                    
                    # Publish loop
                    while wlan.isconnected():
                        global on_valves,NUMBER_OF_WORK,interval_seconds,last_execution_time,current_mode,manual_mode_on_valves
                        # Publish the JSON message at regular intervals
                        
                        interval_period=[seconds_to_timer(seconds) for seconds in interval_seconds]
                        current_time=seconds_to_timer(last_execution_time)
                    
                        if current_mode !="manual":
                            data = {
                                "status": "online",
                                "number_of_valve": NUMBER_OF_WORK,
                                "open_valve": on_valves,
                                "set period": interval_period,
                                "Current Time": current_time,
                                "mode": current_mode,
                                "skipped_valves":[2]
                                }
                            json_message = ujson.dumps(data)
                            client.publish(MQTT_TOPIC_PUB, json_message)
                            #print("on valve",on_valves)
                            #print("current time",current_time )
                            #print(f"Published message: {json_message} to topic: {MQTT_TOPIC_PUB}")
                        else:
                            print("manual mode")
                            data = {
                                "status": "online",
                                "number_of_valve": NUMBER_OF_WORK,
                                "open_valve": manual_mode_on_valves,
                                "set period": interval_period,
                                "Current Time": current_time,
                                "mode": current_mode
                                }
                            json_message = ujson.dumps(data)
                            client.publish(MQTT_TOPIC_PUB, json_message)
                        client.check_msg()  # Non-blocking check for new messages
                        await asyncio.sleep(publish_interval)
                    
                    client.disconnect()
                    print("MQTT Disconnected due to WiFi loss")
                    
                except Exception as e:
                    print(f"MQTT error: {e}. Reconnecting in 5 seconds...")
                    await asyncio.sleep(5)
            else:
                print("Waiting for WiFi to reconnect before connecting to MQTT...")
                await asyncio.sleep(5)

    await connect_wifi()
    
    # Run both maintain_connection and mqtt_task concurrently
    await asyncio.gather(maintain_connection(), mqtt_task())

                        
# Main Task
async def main_task():
    global exit_rest_mode
    global last_execution_time, work, interval_seconds, NUMBER_OF_WORK, batch_size_saved, manual_to_automatic, count, rest_time,save_water_time_saved,current_mode
    last_execution_time, work, interval_seconds, NUMBER_OF_WORK, batch_size_saved, save_water_time_saved = load_state()
    rest_time = 0
    previous_work = None
    save_old_data=0
    skip_valves = [2] 

    while True:
        exit_rest_mode=False
        save_old_data +=1
        if automatic_mode:
            current_mode="automatic"
            manual_mode.off()

            if manual_to_automatic:
                automatic_work_function(work, NUMBER_OF_WORK, batch_size_saved)
                manual_to_automatic = False

            if work > NUMBER_OF_WORK:
                work = NUMBER_OF_WORK

            if previous_work is None or work != previous_work:
                print(work, NUMBER_OF_WORK)
                automatic_work_function(work, NUMBER_OF_WORK, batch_size_saved)
                previous_work = work

            last_execution_time += 1
            if not setting_mode:
                message = ["Automatic mode", f"{seconds_to_timer(last_execution_time)},V:{work},B:{batch_size_saved}"]
                display_message(lcd, message)
                setting_mode_exit()

            if setting_mode or manual_setting_mode:
                count += 1
                if count >= 300:
                    setting_mode_exit()
            save_state(last_execution_time, work, interval_seconds, NUMBER_OF_WORK, batch_size_saved, save_water_time_saved)
            #save data in every minute 
            #if save_old_data==60:
                #save_state(last_execution_time, work, interval_seconds, NUMBER_OF_WORK, batch_size_saved, save_water_time_saved)
                #save_old_data=0
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
                        if save_water_time_saved==60:
                            save_water_time_saved=0
                        # Enter rest period
                        while rest_time < save_water_time_saved:
                            global current_mode
                            global exit_rest_mode
                            current_mode="rest"
                            message = ["Rest mode", f"{seconds_to_timer(rest_time)}"]
                            display_message(lcd, message)
                            rest_time += 1
                            await asyncio.sleep(1)
                            print(exit_rest_mode)
                            print("sikp loop")
                            if exit_rest_mode:
                                print(exit_rest_mode)
                                print("exit")
                                break

                if work > NUMBER_OF_WORK:
                    work = 1
                    rest_time = 0
                    if save_water_time_saved==60:
                        save_water_time_saved=0
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
                        await asyncio.sleep(1)
                        print(exit_rest_mode)
                        print("main loop")
                        save_state(last_execution_time, work, interval_seconds, NUMBER_OF_WORK, batch_size_saved, save_water_time_saved)
                        # save the data every minute
                        #if save_old_data==60:
                            #save_state(last_execution_time, work, interval_seconds, NUMBER_OF_WORK, batch_size_saved, save_water_time_saved)
                            #save_old_data=0
                            
                        set_button.irq(trigger=Pin.IRQ_RISING, handler=setting_function)
                        mode_button.irq(trigger=machine.Pin.IRQ_FALLING, handler=toggle_mode)
                        if setting_mode or not automatic_mode:
                            break

            await asyncio.sleep(1)
            up_button.irq(trigger=Pin.IRQ_RISING, handler=up_button_handler)
            down_button.irq(trigger=Pin.IRQ_RISING, handler=down_button_handler)
            ok_button.irq(trigger=Pin.IRQ_RISING, handler=ok_button_handler)
            set_button.irq(trigger=Pin.IRQ_RISING, handler=setting_function)
        else:
            manual_mode.on()
            current_mode ="manual"
            up_button.irq(handler=None)
            down_button.irq(handler=None)
            ok_button.irq(handler=None)
            set_button.irq(handler=None)
            if not manual_setting_mode:    
                message = ["manual mode", "Activated"]
                display_message(lcd, message)
            handle_buttons()
            await asyncio.sleep(0.1)

        mode_button.irq(trigger=machine.Pin.IRQ_FALLING, handler=toggle_mode)


# Main entry point
async def main():
    # Create tasks for both the main part and the network part
    task1 = asyncio.create_task(main_task())
    task2 = asyncio.create_task(network_task())
    
    # Run both tasks concurrently
    await asyncio.gather(task1, task2)
    
if __name__ == "__main__":
    asyncio.run(main())

