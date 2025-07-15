import wifi_manager
import splitflap_controller
import uasyncio as asyncio
from machine import Pin
import time

wlan = wifi_manager.connect_to_wifi()
if not wlan:
    print("Kein WLAN gespeichert. Starte Setup...")
    asyncio.run(wifi_manager.serve_wifi_setup())
else:
    print("ESP OK – IP:", wlan.ifconfig()[0])
    flaps = splitflap_controller.initialize_flaps()
    splitflap_controller.run_server_sync(flaps)

# Schrittsequenz für 28BYJ-48
STEP_SEQUENCE = [
    [1,0,0,0], [1,1,0,0], [0,1,0,0], [0,1,1,0],
    [0,0,1,0], [0,0,1,1], [0,0,0,1], [1,0,0,1]
]

class SplitFlap:
    def __init__(self, motor_pins, hall_pin, steps_per_flip=16, flaps=40):
        self.motor_pins = [Pin(pin, Pin.OUT) for pin in motor_pins]
        self.hall_sensor = Pin(hall_pin, Pin.IN, Pin.PULL_UP)
        self.steps_per_flip = steps_per_flip
        self.flaps = flaps
        self.position = 0

    def _step(self, index):
        for pin, val in zip(self.motor_pins, STEP_SEQUENCE[index]):
            pin.value(val)

    def rotate_steps(self, steps):
        for _ in range(steps):
            for i in range(len(STEP_SEQUENCE)):
                self._step(i)
                time.sleep_ms(2)

    def home(self):
        for _ in range(500):  # failsafe
            if self.hall_sensor.value() == 0:
                break
            self.rotate_steps(1)
        self.position = 0

    def move_to(self, target):
        steps = ((target - self.position) % self.flaps) * self.steps_per_flip
        self.rotate_steps(steps)
        self.position = target

# Initialisiere Split-Flap-Module
flaps = [
    SplitFlap([18, 19, 21, 22], 23),  # Modul 1
    SplitFlap([14, 27, 26, 25], 15),  # Modul 2
]

for flap in flaps:
    print("Homing...")
    flap.home()

drink_count = 0

# Webserver für Steuerung
async def handle_client(reader, writer):
    global drink_count
    req = await reader.readline()
    print("Request:", req)
    if b"/inc" in req:
        drink_count += 1
        text = str(drink_count).zfill(len(flaps))
        for i, digit in enumerate(text):
            flaps[i].move_to(int(digit))
        response = "HTTP/1.0 200 OK\r\n\r\nCount: " + str(drink_count)
    else:
        response = "HTTP/1.0 200 OK\r\n\r\nUse /inc to increment count"
    await writer.awrite(response)
    await writer.aclose()

async def run_server():
    server = await asyncio.start_server(handle_client, "0.0.0.0", 80)
    print("Webserver gestartet auf Port 80")
    await server.wait_closed()

# Starte Server
asyncio.run(run_server())
