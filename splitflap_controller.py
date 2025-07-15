# splitflap_controller.py
import time
import socket
from machine import Pin

STEP_SEQUENCE = list(reversed([
    [1, 0, 0, 0], [1, 1, 0, 0], [0, 1, 0, 0], [0, 1, 1, 0],
    [0, 0, 1, 0], [0, 0, 1, 1], [0, 0, 0, 1], [1, 0, 0, 1]
]))

FLAP_CHARS = [" "] + [str(i) for i in range(1, 10)] + ["0"]  # [' ', '1', ..., '9', '0']

class SplitFlap:
    def __init__(self, motor_pins, hall_pin, steps_per_flip=16, flaps=16, offset=0):
        self.motor_pins = [Pin(pin, Pin.OUT) for pin in motor_pins]
        self.hall_sensor = Pin(hall_pin, Pin.IN, Pin.PULL_UP)
        self.steps_per_flip = steps_per_flip
        self.flaps = flaps
        self.offset = offset
        self.position = 0

    def _step(self, step_index):
        for pin, val in zip(self.motor_pins, STEP_SEQUENCE[step_index]):
            pin.value(val)

    def rotate_steps(self, steps):
        for _ in range(steps):
            for i in range(len(STEP_SEQUENCE)):
                self._step(i)
                time.sleep_ms(2)

    def home(self):
        print("Starte Homing...")
        last_val = 1
        for _ in range(800):
            val = self.hall_sensor.value()
            if val == 0 and last_val == 1:
                print("Hallsensor erkannt → Nullposition")
                self.rotate_steps((self.offset + 1) * self.steps_per_flip)
                break
            self.rotate_steps(1)
            last_val = val
        self.position = 0

    def move_to(self, target_flap):
        steps_needed = ((target_flap - self.position) % self.flaps) * self.steps_per_flip
        self.rotate_steps(steps_needed)
        self.position = target_flap

    def move_to_char(self, char):
        if char not in FLAP_CHARS:
            print(f"Zeichen {char} wird ignoriert")
            return
        target_index = FLAP_CHARS.index(char)
        self.move_to(target_index)

def initialize_flaps():
    flaps = [
        SplitFlap([18, 19, 21, 22], 23, offset=15),  # Modul 1
        SplitFlap([14, 27, 26, 25], 15, offset=11),  # Modul 2
    ]
    for flap in flaps:
        flap.home()
    return flaps

def run_server_sync(flaps):
    global drink_count
    drink_count = 0

    addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
    s = socket.socket()
    s.bind(addr)
    s.listen(1)
    print("Webserver gestartet")

    while True:
        cl, addr = s.accept()
        print("Client verbunden:", addr)
        try:
            req = cl.recv(1024)
            req_str = req.decode()
            print("Request:", req_str)

            if "GET /inc" in req_str:
                prev_count = drink_count
                drink_count += 1
                count_str = "{:0{w}}".format(drink_count, w=len(flaps))
                prev_str  = "{:0{w}}".format(prev_count,  w=len(flaps))
                for i in range(len(flaps)):
                    if count_str[i] != prev_str[i]:
                        flaps[i].move_to_char(count_str[i])
                response = (
                    "HTTP/1.0 303 See Other\r\n"
                    "Location: /\r\n\r\n"
                )

            elif "GET /sync" in req_str:
                for flap in flaps:
                    flap.home()
                response = (
                    "HTTP/1.0 303 See Other\r\n"
                    "Location: /\r\n\r\n"
                )

            elif "GET / " in req_str or "GET /HTTP" in req_str:
                body = (
                    "<html><head><title>Drinkzähler</title></head><body>"
                    "<h2>Drinkzähler</h2>"
                    "<form action='/inc' method='get'>"
                    "<button type='submit'>+1 Drink</button>"
                    "</form>"
                    "<form action='/sync' method='get'>"
                    "<button type='submit'>Synchronisieren</button>"
                    "</form>"
                    "</body></html>"
                )
                response = (
                    "HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n" + body
                )
            else:
                response = "HTTP/1.0 404 Not Found\r\n\r\nSeite nicht gefunden."

            cl.send(response)
        except Exception as e:
            print("Fehler:", e)
        finally:
            cl.close()
