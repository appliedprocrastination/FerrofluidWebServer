import socket
import time
import network
from machine import Pin, Timer, PWM, I2C
import uasyncio as asyncio
import gc # Garbage collection

# Define config:
PWM_FREQ = 1000

class Magnet(PWM):
    state = False
    PWM_MAX = 65535 # Max duty cycle
    TURN_OFF_DELAY = 400 # ms
    MAX_ON_TIME = 10000 # ms
    def __init__(self, pin, identifier, frequency=1000, duty_cycle=100):
        # Duty cycle in percent
        super().__init__(pin)
        self.identifier = identifier
        self.frequency = frequency
        self.duty = int((duty_cycle / 100) * self.PWM_MAX)
        self.freq(frequency)
        self.time_at_turnoff = time.ticks_ms()
        self.time_at_turn_on = 0
         
    def toggle(self):
        if self.state:
            self.turn_off()
        else:
            self.turn_on()
            
    def turn_on(self):
        self.duty_u16(self.duty)
        self.state = True
        self.preliminary_state = True
        self.time_at_turn_on = time.ticks_ms()
        
    def turn_off(self):
        if self.state and self.preliminary_state:
            # Keep the magnet on for TURN_OFF_DELAY ms in order to transfer to other magnets more easily.
            # This requires self.update() to be called continuously
            self.time_at_turnoff = time.ticks_ms()
            self.preliminary_state = False
        else:
            self.duty_u16(0)
            self.state = False
        
    def update(self, time_now):
        if (self.state and not self.preliminary_state and self.TURN_OFF_DELAY - (time_now - self.time_at_turnoff) <= 0 ) \
           or (self.state and self.MAX_ON_TIME - (time_now - self.time_at_turn_on) <= 0):
            # Turn off magnet after TURN_OFF_DELAY if a new magnet has been turned on to easily move ferrofluid around
            # (this feels interactive and fun, but makes it impossible to draw shapes, so another mode should be implemented for that)
            # or: Turn off magnet after MAX_ON_TIME to save power.
            self.turn_off()
        

# Define magnets:
M1 = Magnet(Pin(26), 1)
M2 = Magnet(Pin(22), 2)
M3 = Magnet(Pin(21), 3)
M4 = Magnet(Pin(20), 4)
M5 = Magnet(Pin(19), 5)
M6 = Magnet(Pin(18), 6)
M7 = Magnet(Pin(17), 7)
M8 = Magnet(Pin(16), 8)
M9 = Magnet(Pin(15), 9)
M10 = Magnet(Pin(14), 10)
M11 = Magnet(Pin(13), 11)
M12 = Magnet(Pin(12), 12)
magnets = [[M1,M2,M3,M4],[M5,M6,M7,M8],[M9,M10,M11,M12]]

            
def toggle_magnets(magnets, magnets_to_toggle):
    i = 0
    for x in range(len(magnets)):
        for y in range(len(magnets[x])):
            i += 1
            if i in magnets_to_toggle:
                m = magnets[x][y]
                m.toggle()
            else:
                m = magnets[x][y]
                m.turn_off()
                

ssid = 'MySSID'
password = 'MyPassword'

wlan = network.WLAN(network.STA_IF)
host_port = 80

def get_html(html_name):
    with open(html_name, 'r') as file:
        html = file.read()
    status = wlan.ifconfig()
    html = html.replace("HOST_ADDR", status[0])
    html = html.replace("HOST_PORT", str(host_port))

    return html

def extract_ajax_payload(response_string):
    # Hardcoded and fragile function for extracting very specific ajax request.
    start = 16 #Hardcoded value for len('/magnet?num=')+4 that assumes ajax request for a magnet starts at index 4
    stop = response_string[start:-1].find("HTTP")
    return response_string[start:start+stop].strip()

def connect_to_network():
    wlan.active(True)
    wlan.config(pm = 0xa11140)  # Disable power-save mode
    wlan.connect(ssid, password)

    max_wait = 10
    while max_wait > 0:
        if wlan.status() < 0 or wlan.status() >= 3:
            break
        max_wait -= 1
        print('waiting for connection...')
        time.sleep(1)

    if wlan.status() != 3:
        raise RuntimeError('network connection failed')
    else:
        print('connected')
        status = wlan.ifconfig()
        print('ip = ' + status[0])
        
async def serve_client(reader, writer):
    try:
        gc.collect()

        request = await reader.read(1024)
        #request = str(request_line)
        request = request.decode("utf-8")
        #print('request = %s' % str(request))
        response = ""
        if request.find('/magnet?num=') == 4:
            try:
                mag_idx = int(extract_ajax_payload(request))
                response = f"Enabling: {mag_idx}"
                print(response)
                toggle_magnets(magnets,[mag_idx])
            except ValueError:
                print(f"Couldn't find payload in request:\n\n{request}")
        # Load html and replace with current data 
        else:
            #print(request)
            response = get_html('index.html')
            
        writer.write('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
        writer.write(response)
    
        await writer.drain()
        await writer.wait_closed()
        gc.collect()
    except OSError:
        pass

def main():
    print('Connecting to Network...')
    connect_to_network()

    print('Setting up webserver...')
    asyncio.create_task(asyncio.start_server(serve_client, "0.0.0.0", host_port))
    
    print('Starting main loop:')
    gc.collect()
    while True:
        time_now = time.ticks_ms()
        for row in magnets:
            for m in row:
                m.update(time_now)
        gc.collect()
        await asyncio.sleep(0.05)

try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()

    