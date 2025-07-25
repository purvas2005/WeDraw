import os
import socket
import threading
import tkinter as tk
from tkinter import ttk, messagebox, colorchooser, simpledialog
import ssl
from PIL import Image, ImageTk
import math

HOST = "10.30.204.222"   #replace with your server's IP address
PORT = 5555
BUFFER_SIZE = 1024
CERTIFICATE_PATH = "certificate.pem"    #set as per the path of the certificate you have generated

class WhiteboardClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Collaborative Whiteboard")
        self.root.geometry("1000x700")
        self.root.configure(bg="#f0f0f0")

        # Initialize variables
        self.colour = "#000000"
        self.shapes = []
        self.prev_x, self.prev_y = None, None
        self.current_tool = "pen"   #default tool is the pen
        self.line_width = 2
        self.colour_history = ["#000000", "#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#FF00FF"] #default colours, which can be changed

        self.create_ui()    #create the ui before trying to connect so that race condition doesnt occure between create_ui and receive_data
        self.setup_connection()

    def setup_connection(self):
        try:
            raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            context.load_verify_locations(CERTIFICATE_PATH)  
            context.check_hostname = False      #false here because otherwise new certificate will have to be generated each time IP changes
            context.verify_mode = ssl.CERT_REQUIRED

            self.client_socket = context.wrap_socket(raw_socket, server_hostname=HOST)
            self.client_socket.connect((HOST, PORT))

            # Start receiving data from other clients via server
            receive_thread = threading.Thread(target=self.receive_data)
            receive_thread.daemon = True
            receive_thread.start()

        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect to server: {e}")
            exit(1)

    def create_ui(self):

        main_frame = tk.Frame(self.root, bg="#f0f0f0")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        #Basic layout of the whiteboard window
        tool_panel = tk.Frame(main_frame, bg="#e0e0e0", width=120)
        tool_panel.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        title_label = tk.Label(tool_panel, text="Whiteboard", font=("Arial", 16, "bold"), bg="#e0e0e0")
        title_label.pack(pady=10)

        # buttons
        self.create_tool_button(tool_panel, "✏️ Pen", lambda: self.set_tool("pen"))
        self.create_tool_button(tool_panel, "⬜ Rectangle", lambda: self.set_tool("rectangle"))
        self.create_tool_button(tool_panel, "⭕ Circle", lambda: self.set_tool("circle"))
        self.create_tool_button(tool_panel, "📝 Text", lambda: self.set_tool("text"))
        self.create_tool_button(tool_panel, "↩️ Undo", self.undo)
        self.create_tool_button(tool_panel, "🧹 Clear All", self.clear_canvas)

        # width change slider
        tk.Label(tool_panel, text="Line Width:", bg="#e0e0e0").pack(pady=(15, 0))
        self.width_slider = tk.Scale(tool_panel, from_=1, to=10, orient=tk.HORIZONTAL,
                                    command=self.set_line_width, bg="#e0e0e0")
        self.width_slider.set(2)
        self.width_slider.pack(pady=(0, 15), padx=10, fill=tk.X)

        # colours and colour wheel
        tk.Label(tool_panel, text="Colors:", bg="#e0e0e0").pack()
        colour_frame = tk.Frame(tool_panel, bg="#e0e0e0")
        colour_frame.pack(pady=5)
        self.create_colour_wheel(tool_panel)

        # Recent colours
        recent_colours_frame = tk.Frame(tool_panel, bg="#e0e0e0")
        recent_colours_frame.pack(pady=10, fill=tk.X)

        for i, colour in enumerate(self.colour_history):
            btn = tk.Button(recent_colours_frame, bg=colour, width=2, height=1,
                          command=lambda c=colour: self.set_colour(c))
            btn.grid(row=0, column=i, padx=2)

        # Colour picker
        self.create_tool_button(tool_panel, "🎨 Custom Colour", self.choose_colour)

        # Status label
        self.status_label = tk.Label(tool_panel, text="Connected", fg="green", bg="#e0e0e0")
        self.status_label.pack(side=tk.BOTTOM, pady=10)

        # Canvas where u can draw
        canvas_frame = tk.Frame(main_frame, bg="white", bd=2, relief=tk.SUNKEN)
        canvas_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.canvas = tk.Canvas(canvas_frame, bg="white", cursor="crosshair")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)

        # Temporary shape for drawing
        self.temp_shape = None
        self.start_x, self.start_y = None, None

    #function to create the various tool buttons 
    def create_tool_button(self, parent, text, command):
        btn = tk.Button(parent, text=text, command=command, bg="#d0d0d0", relief=tk.RAISED, width=12, height=1)
        btn.pack(pady=3, padx=5, fill=tk.X)
        return btn

    #func to create the colour wheel
    def create_colour_wheel(self, parent):
        canvas_size = 100
        wheel_radius = 45

        colour_canvas = tk.Canvas(parent, width=canvas_size, height=canvas_size, bg="#e0e0e0", highlightthickness=0)
        colour_canvas.pack(pady=5)

        # Draw colour wheel by mapping angle to rgb value to get a smooth gradient
        for angle in range(0, 360, 3):
            r = wheel_radius
            x1 = canvas_size/2 + r * math.cos(math.radians(angle))
            y1 = canvas_size/2 + r * math.sin(math.radians(angle))
            x2 = canvas_size/2 + r * math.cos(math.radians(angle+5))
            y2 = canvas_size/2 + r * math.sin(math.radians(angle+5))

            h = angle / 360.0
            r, g, b = self.hsv_to_rgb(h, 1, 1)
            hex_colour = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

            colour_canvas.create_polygon(canvas_size/2, canvas_size/2, x1, y1, x2, y2, fill=hex_colour, outline="")

        # Add white center and black ring
        colour_canvas.create_oval(canvas_size/2-wheel_radius/3, canvas_size/2-wheel_radius/3,
                               canvas_size/2+wheel_radius/3, canvas_size/2+wheel_radius/3,
                               fill="white", outline="#d0d0d0")

        colour_canvas.create_oval(canvas_size/2-wheel_radius, canvas_size/2-wheel_radius,
                               canvas_size/2+wheel_radius, canvas_size/2+wheel_radius,
                               outline="black", width=1)

        colour_canvas.bind("<Button-1>", self.colour_wheel_click)

    #func to handle click on colour wheel to select a colour
    def colour_wheel_click(self, event):
        canvas_size = 100
        wheel_radius = 45
        center_x, center_y = canvas_size/2, canvas_size/2

        #find where the click was, and then map it to the rgb value as per the wheel created earlier
        dx = event.x - center_x
        dy = event.y - center_y
        distance = math.sqrt(dx*dx + dy*dy)

        if distance <= wheel_radius:
            angle = math.degrees(math.atan2(dy, dx))
            if angle < 0:
                angle += 360

            h = angle / 360.0
            r, g, b = self.hsv_to_rgb(h, 1, 1)
            hex_colour = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

            self.set_colour(hex_colour)

    def hsv_to_rgb(self, h, s, v):
        if s == 0.0:
            return v, v, v

        i = int(h * 6)
        f = (h * 6) - i
        p = v * (1 - s)
        q = v * (1 - s * f)
        t = v * (1 - s * (1 - f))

        i %= 6
        if i == 0:
            return v, t, p
        elif i == 1:
            return q, v, p
        elif i == 2:
            return p, v, t
        elif i == 3:
            return p, q, v
        elif i == 4:
            return t, p, v
        else:
            return v, p, q

    #func to change tool and display current tool on title bar
    def set_tool(self, tool):
        self.current_tool = tool
        self.root.title(f"Collaborative Whiteboard - {tool.capitalize()}")

    #func to set linewidth
    def set_line_width(self, width):
        self.line_width = int(width)

    #func to set the colour based on user choice and modify colour history to keep 6 most recent colours
    def set_colour(self, colour):
        self.colour = colour

        if colour in self.colour_history:
            self.colour_history.remove(colour)
        self.colour_history.insert(0, colour)
        self.colour_history = self.colour_history[:6]  

    #func to take the users choice and call set_colour with the choice as argument
    def choose_colour(self):
        colour = colourchooser.askcolour(initialcolour=self.colour)[1]
        if colour:
            self.set_colour(colour)

    #mouse down event for the whiteboard, for drawing purpose
    def on_mouse_down(self, event):
        self.start_x, self.start_y = event.x, event.y
        self.prev_x, self.prev_y = event.x, event.y

        if self.current_tool == "text":
            text = simpledialog.askstring("Text", "Enter text:")
            if text:
                self.add_text(event.x, event.y, text)
                self.send_data(f"TEXT {event.x} {event.y} {self.colour} {text}")

    #mouse drag event for pen, rectangle and circle
    def on_mouse_drag(self, event):
        if self.current_tool == "pen":  #draws a line with mousedrag
            self.draw_line(self.prev_x, self.prev_y, event.x, event.y)
            self.send_data(f"LINE {self.prev_x} {self.prev_y} {event.x} {event.y} {self.colour} {self.line_width}")
            self.prev_x, self.prev_y = event.x, event.y
        
        #draws rect or circle on mousedrag by clearing buffer (temp_shape) and then drawing new shape
        elif self.current_tool in ["rectangle", "circle"]: 
            if self.temp_shape:
                self.canvas.delete(self.temp_shape)

            if self.current_tool == "rectangle":
                self.temp_shape = self.canvas.create_rectangle(
                    self.start_x, self.start_y, event.x, event.y,
                    outline=self.colour, width=self.line_width
                )
                
            elif self.current_tool == "circle":
                radius = math.sqrt((event.x - self.start_x)**2 + (event.y - self.start_y)**2)
                self.temp_shape = self.canvas.create_oval(
                    self.start_x - radius, self.start_y - radius,
                    self.start_x + radius, self.start_y + radius,
                    outline=self.colour, width=self.line_width
                )

    def on_mouse_up(self, event):
        if self.current_tool == "rectangle":
            if self.temp_shape:
                self.canvas.delete(self.temp_shape)

            shape = self.canvas.create_rectangle(
                self.start_x, self.start_y, event.x, event.y,
                outline=self.colour, width=self.line_width
            )
            self.shapes.append(shape)
            self.send_data(f"RECT {self.start_x} {self.start_y} {event.x} {event.y} {self.colour} {self.line_width}")

        elif self.current_tool == "circle":
            if self.temp_shape:
                self.canvas.delete(self.temp_shape)

            radius = int(math.sqrt((event.x - self.start_x)**2 + (event.y - self.start_y)**2))
            shape = self.canvas.create_oval(
                self.start_x - radius, self.start_y - radius,
                self.start_x + radius, self.start_y + radius,
                outline=self.colour, width=self.line_width
            )
            self.shapes.append(shape)
            self.send_data(f"CIRC {self.start_x} {self.start_y} {radius} {self.colour} {self.line_width}")

        self.temp_shape = None
        self.prev_x, self.prev_y = None, None
        self.start_x, self.start_y = None, None

    def draw_line(self, x1, y1, x2, y2):
        shape = self.canvas.create_line(x1, y1, x2, y2, fill=self.colour, width=self.line_width, smooth=True, capstyle=tk.ROUND)
        self.shapes.append(shape)

    def add_text(self, x, y, text):
        shape = self.canvas.create_text(x, y, text=text, fill=self.colour, font=("Arial", 12))
        self.shapes.append(shape)

    def undo(self, from_server=False):
        if self.shapes:
            shape = self.shapes.pop()
            self.canvas.delete(shape)

            if not from_server:
                self.send_data("UNDO")

    def clear_canvas(self, from_server=False):
        self.canvas.delete("all")
        self.shapes = []

    def send_data(self, data):
        try:
            message = data.encode()
            message_length = len(message)
            self.client_socket.sendall(message_length.to_bytes(4, 'big'))
            self.client_socket.sendall(message)
        except Exception as e:
            print(f"Send error details: {str(e)}")  # Add detailed logging
            self.status_label.config(text=f"Disconnected: {str(e)}", fg="red")
            messagebox.showerror("Error", f"Failed to send data: {e}")

    def receive_data(self):
        while True:
            try:
                message_length = int.from_bytes(self.client_socket.recv(4), 'big')
                data = self.client_socket.recv(message_length).decode()

                if not data:
                    break

                self.process_command(data)
            except Exception as e:
                print(f"Receive error details: {str(e)}")  
                self.status_label.config(text=f"Disconnected: {str(e)}", fg="red")
                messagebox.showerror("Error", f"Failed to receive data: {e}")
                break

    def process_command(self, data):
        commands = data.split("\n")
        for command in commands:
            parts = command.split()
            if not parts:
                continue

            cmd = parts[0]

            if cmd == "LINE" and len(parts) >= 6:
                x1, y1, x2, y2 = map(int, parts[1:5])
                colour = parts[5]
                width = int(parts[6]) if len(parts) > 6 else 2

                shape = self.canvas.create_line(x1, y1, x2, y2, fill=colour, width=width, smooth=True, capstyle=tk.ROUND)
                self.shapes.append(shape)

            elif cmd == "RECT" and len(parts) >= 6:
                x1, y1, x2, y2 = map(int, parts[1:5])
                colour = parts[5]
                width = int(parts[6]) if len(parts) > 6 else 2

                shape = self.canvas.create_rectangle(x1, y1, x2, y2, outline=colour, width=width)
                self.shapes.append(shape)

            elif cmd == "CIRC" and len(parts) >= 5:
                x, y, radius = map(int, parts[1:4])
                colour = parts[4]
                width = int(parts[5]) if len(parts) > 5 else 2

                shape = self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, outline=colour, width=width)
                self.shapes.append(shape)

            elif cmd == "TEXT" and len(parts) >= 4:
                x, y = map(int, parts[1:3])
                colour = parts[3]
                text = " ".join(parts[4:])

                shape = self.canvas.create_text(x, y, text=text, fill=colour, font=("Arial", 12))
                self.shapes.append(shape)

            elif cmd == "UNDO":
                self.undo(from_server=True)

            elif cmd == "CLEAR":
                self.clear_canvas(from_server=True)

            else:
                print(f"Unknown command: {command}")

def main():
    root = tk.Tk()
    app = WhiteboardClient(root)
    root.mainloop()

if __name__ == "__main__":
    main()
