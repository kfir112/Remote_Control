import socket
import threading
from threading import Lock
from pynput.keyboard import Key, Listener
from pynput.mouse import Listener as MouseListener
import tkinter as tk
from PIL import Image, ImageTk
import io
import signal
import sys

#press alt + F4 to exit screen while program is working, Esc will not work.

class ScreenReceiver:
    def __init__(self, host="192.168.68.111", port=1338,tk_root=None):
        self.host = host
        self.port = port
        self.tk_root = tk_root
        self.sock = None
        self.conn = None
        self.running = False

        self.latest_image = None
        self.lock = Lock()

        self.root = tk_root or tk.Tk()
        self.root.title("Remote Screen Viewer")
        self.label = tk.Label(self.root)
        self.label.pack()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def start(self):
        self.running = True
        threading.Thread(target=self.listen_for_connection, daemon=True).start()
        self.update_image_loop()

    def listen_for_connection(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.bind((self.host, self.port))
            self.sock.listen(1)
            print(f"[ScreenReceiver] Listening on {self.host}:{self.port}...")

            self.conn, addr = self.sock.accept()
            print(f"[ScreenReceiver] Connection from {addr}")

            while self.running:
                size_data = self.conn.recv(4)
                if not size_data:
                    print("[ScreenReceiver] No size data. Connection closed.")
                    break

                size = int.from_bytes(size_data, byteorder='big')
                buffer = b""
                while len(buffer) < size:
                    packet = self.conn.recv(size - len(buffer))
                    if not packet:
                        print("[ScreenReceiver] Incomplete frame data. Connection closed.")
                        return
                    buffer += packet

                try:
                    image = Image.open(io.BytesIO(buffer))
                    with self.lock:
                        self.latest_image = image
                except Exception as e:
                    print(f"[ScreenReceiver] Error decoding image: {e}")
                    continue

        except Exception as e:
            print(f"[ScreenReceiver] Error: {e}")
        finally:
            self.cleanup()

    def update_image_loop(self):
        try:
            with self.lock:
                if self.latest_image:
                    screen_width = self.root.winfo_screenwidth()
                    screen_height = self.root.winfo_screenheight()
                    resized = self.latest_image.resize((screen_width, screen_height), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(resized)
                    self.label.config(image=photo)
                    self.label.image = photo
        except Exception as e:
            print(f"[ScreenReceiver] UI update error: {e}")

        if self.running:
            self.root.after(100, self.update_image_loop)


    def on_close(self):
        print("[ScreenReceiver] Closing...")
        self.running = False
        self.cleanup()
        self.root.destroy()

    def cleanup(self):
        try:
            if self.conn:
                self.conn.close()
        except:
            pass
        try:
            if self.sock:
                self.sock.close()
        except:
            pass


# shutdown on Ctrl+C
def handle_exit(sig, frame):
    print("[Main] Caught termination signal. Exiting...")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_exit)


def create_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("192.168.68.111", 1337))
    server_socket.listen(1)
    print(f"Listening for new connections")
    return server_socket


def accept_client(server_socket):
    client_socket, client_address = server_socket.accept()
    print(f"Connection established with {client_address}")
    return client_socket


def keyboard_thread(client_sock):
    def on_press(key):
        try:
            msg = f"{key.char}\n"
        except AttributeError:
            msg = f"{key}\n"
        
        try:
            print(f"Sending key: {msg.strip()}")
            client_sock.sendall(msg.encode())
        except (BrokenPipeError, ConnectionResetError):
            print("Client disconnected. Stopping keyboard listener.")
            return False
        except Exception as e:
            print(f"Unexpected error: {e}")
            return False
            
    with Listener(on_press=on_press) as listener:
        listener.join()

def mouse_thread(client_sock):
    def on_move(x, y):
        try:
            msg = f"MOVE:{x},{y}\n"
            print(msg)
            client_sock.sendall(msg.encode())
        except (BrokenPipeError, ConnectionResetError):
            print("Client disconnected.")
            return False
        except Exception as e:
            print(f"Mouse move error: {e}")
            return False

    def on_click(x, y, button, pressed):
        try:
            action = "DOWN" if pressed else "UP"
            msg = f"CLICK:{x},{y},{button.name},{action}\n"
            print(msg)
            client_sock.sendall(msg.encode())
        except (BrokenPipeError, ConnectionResetError):
            print("Client disconnected.")
            return False
        except Exception as e:
            print(f"Mouse click error: {e}")
            return False

    def on_scroll(x, y, dx, dy):
        try:
            msg = f"SCROLL:{x},{y},{dx},{dy}\n"
            print(msg)
            client_sock.sendall(msg.encode())
        except (BrokenPipeError, ConnectionResetError):
            print("Client disconnected.")
            return False
        except Exception as e:
            print(f"Mouse scroll error: {e}")
            return False

    with MouseListener(on_move=on_move, on_click=on_click, on_scroll=on_scroll) as listener:
        listener.join()


if __name__ == "__main__":
    server_sock = create_server()
    client_sock = accept_client(server_sock)

    root = tk.Tk()
    root.attributes("-topmost", True)
    root.attributes("-fullscreen", True)

    #root.state('zoomed') #to see taskbar

    screen_receiver = ScreenReceiver(host="192.168.68.111", port=1338, tk_root=root)
    screen_receiver.start()

    def on_main_close():
        print("[Main] Closing main application...")

        screen_receiver.on_close()

        try:
            client_sock.shutdown(socket.SHUT_RDWR)
            client_sock.close()
        except:
            pass
        try:
            server_sock.close()
        except:
            pass
    
    root.protocol("WM_DELETE_WINDOW", on_main_close)

    kb_thread = threading.Thread(target=keyboard_thread, args=(client_sock,),daemon=True)
    mouse_thread_ = threading.Thread(target=mouse_thread, args=(client_sock,),daemon=True)

    kb_thread.start()
    mouse_thread_.start()

    root.mainloop()
