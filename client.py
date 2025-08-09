import socket
import threading
from pynput.keyboard import Controller, Key
from pynput.mouse import Controller as MouseController, Button
from PIL import ImageGrab
import io
import time
import signal
import sys
import pyautogui
from PIL import ImageDraw

special_keys = {
    "Key.alt": Key.alt,
    "Key.alt_gr": Key.alt_gr,
    "Key.backspace": Key.backspace,
    "Key.caps_lock": Key.caps_lock,
    "Key.cmd": Key.cmd,
    "Key.ctrl": Key.ctrl,
    "Key.delete": Key.delete,
    "Key.down": Key.down,
    "Key.end": Key.end,
    "Key.enter": Key.enter,
    "Key.esc": Key.esc,
    "Key.f1": Key.f1,
    "Key.f2": Key.f2,
    "Key.f3": Key.f3,
    "Key.f4": Key.f4,
    "Key.f5": Key.f5,
    "Key.f6": Key.f6,
    "Key.f7": Key.f7,
    "Key.f8": Key.f8,
    "Key.f9": Key.f9,
    "Key.f10": Key.f10,
    "Key.f11": Key.f11,
    "Key.f12": Key.f12,
    "Key.home": Key.home,
    "Key.insert": Key.insert,
    "Key.left": Key.left,
    "Key.menu": Key.menu,
    "Key.num_lock": Key.num_lock,
    "Key.page_down": Key.page_down,
    "Key.page_up": Key.page_up,
    "Key.pause": Key.pause,
    "Key.print_screen": Key.print_screen,
    "Key.right": Key.right,
    "Key.scroll_lock": Key.scroll_lock,
    "Key.shift": Key.shift,
    "Key.shift_l": Key.shift_l,
    "Key.shift_r": Key.shift_r,
    "Key.space": Key.space,
    "Key.tab": Key.tab,
    "Key.up": Key.up
}

keyboard = Controller()
mouse = MouseController()

def create_client():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # Create TCP Socket object
    client_socket.connect(("192.168.68.111", 1337))
    print("Client connected")
    return client_socket


class ScreenSender:
    def __init__(self, server_ip="192.168.68.111", port=1338, interval=0.2):
        self.server_ip = server_ip
        self.port = port
        self.interval = interval
        self.sock = None
        self.running = False

    def start(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.server_ip, self.port))
            self.running = True
            print("[ScreenSender] Connected to screen receiver")

            while self.running:
                image = ImageGrab.grab()
                cursor_x, cursor_y = pyautogui.position()
                draw = ImageDraw.Draw(image)
                draw.ellipse((cursor_x - 5, cursor_y - 5, cursor_x + 5, cursor_y + 5), fill="red")
                with io.BytesIO() as buffer:
                    image.save(buffer, format="JPEG", quality=70)
                    data = buffer.getvalue()

                size = len(data).to_bytes(4, byteorder='big')
                self.sock.sendall(size + data)

                time.sleep(self.interval)
        except (ConnectionRefusedError, ConnectionResetError) as e:
            print(f"[ScreenSender] Connection error: {e}")
        except Exception as e:
            print(f"[ScreenSender] Unexpected error: {e}")
        finally:
            self.cleanup()

    def stop(self):
        self.running = False
        self.cleanup()
    
    def cleanup(self):
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass

#shutdown on Ctrl+C
def handle_exit(sig, frame):
    print("[Main] Caught termination signal. Exiting...")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_exit)

def handle_input(client_socket):
    try:
        buffer = ""
        while True:
            data = client_socket.recv(1024)
            if not data:
                break
            data = data.decode()
            buffer += data

            while '\n' in buffer:
                msg, buffer = buffer.split('\n', 1)
                process_command(msg)
    except ConnectionResetError:
        print("Connection was reset by server.")
    except Exception as e:
        print(f"Unexpected error: {e}")

def process_command(msg):
    try:
        if msg.startswith("MOVE:"):
            try:
                coords = msg[5:]
                x, y = map(int, coords.split(","))
                mouse.position = (x, y)
            except ValueError:
                print(f"Invalid MOVE command: {msg}")
        elif msg.startswith("CLICK:"):
            try:
                x, y, btn, action = msg.split(":")[1].split(",")
                x, y = int(x), int(y)
                mouse.position = (x, y)
                button_map = {
                    "left": Button.left,
                    "right": Button.right,
                    "middle": Button.middle
                }
                button = button_map.get(btn)
                if action == "DOWN":
                    mouse.press(button)
                else:
                    mouse.release(button)
            except Exception as e:
                print(f"Invalid CLICK command: {msg} ({e})")
        elif msg.startswith("SCROLL:"):
                # Format: SCROLL:x,y,dx,dy
                _, payload = msg.split(":", 1)
                x, y, dx, dy = payload.split(",")
                mouse.position = (int(x), int(y))
                mouse.scroll(int(dx), int(dy))
        elif msg.startswith("Key."):
            key = msg
            try:
                k = getattr(Key, key[4:])
                keyboard.press(k)
                keyboard.release(k)
            except AttributeError:
                print(f"Unknown key: {key}")
        else:
            keyboard.press(msg)
            keyboard.release(msg)
    except KeyboardInterrupt:
        raise
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    client_socket = create_client()
    screen_sender = ScreenSender(server_ip="192.168.68.111")

    listener_thread = threading.Thread(target=handle_input, args=((client_socket,)),daemon=True)
    sender_thread = threading.Thread(target=screen_sender.start, daemon=True)

    listener_thread.start()
    sender_thread.start()

    listener_thread.join()
    sender_thread.join()
