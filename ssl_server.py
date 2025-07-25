import os
import socket
import threading
import ssl
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('WhiteboardServer')

HOST = ""  # Listen on all interfaces
PORT = 5555
BUFFER_SIZE = 1024
CERTFILE_PATH = "certificate.pem"
KEYFILE_PATH = "key.pem"

# Dictionary to store connected clients
clients = {}

# List to store drawing history for new clients
drawing_history = []
MAX_HISTORY_SIZE = 100  # Limit history size to prevent memory issues

def handle_client(client_socket, address):
    client_id = f"{address[0]}:{address[1]}"
    logger.info(f"New connection from {client_id}")

    try:
        # Send drawing history to new client
        for cmd in drawing_history:
            try:
                message = cmd.encode()
                message_length = len(message)
                client_socket.sendall(message_length.to_bytes(4, 'big'))
                client_socket.sendall(message)
                time.sleep(0.01)  # Small delay to prevent overwhelming the client
            except Exception as e:
                logger.error(f"Error sending history to client {client_id}: {e}")
                break

        # Handle client messages
        while True:
            message_length = int.from_bytes(client_socket.recv(4), 'big')
            if message_length <= 0:
                break

            data = client_socket.recv(message_length).decode()
            if not data:
                break

            logger.debug(f"Received from {client_id}: {data[:50]}...")

            # Store commands that modify the canvas in history
            if data.startswith(("LINE", "RECT", "CIRC", "TEXT")):
                drawing_history.append(data)
                # Trim history if it gets too long
                if len(drawing_history) > MAX_HISTORY_SIZE:
                    drawing_history.pop(0)
            elif data == "CLEAR":
                drawing_history.clear()
            elif data == "UNDO" and drawing_history:
                drawing_history.pop()

            # Broadcast to all clients
            broadcast(data, client_socket)
    except Exception as e:
        logger.error(f"Error handling client {client_id}: {e}")
    finally:
        client_socket.close()
        if client_socket in clients:
            del clients[client_socket]
        logger.info(f"Connection closed for {client_id}")

def broadcast(message, sender_socket):
    dropped_clients = []

    for client_socket in clients:
        if client_socket != sender_socket:
            try:
                message_bytes = message.encode()
                message_length = len(message_bytes)
                client_socket.sendall(message_length.to_bytes(4, 'big'))
                client_socket.sendall(message_bytes)
            except Exception as e:
                logger.error(f"Error broadcasting to client {clients[client_socket]}: {e}")
                dropped_clients.append(client_socket)

    # Remove dropped clients
    for client in dropped_clients:
        if client in clients:
            del clients[client]

def main():
    # Create server socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((HOST, PORT))
        server_socket.listen(5)
        logger.info(f"Server started on {HOST if HOST else '*'}:{PORT}")

        # Create SSL context
        try:
            context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            context.load_cert_chain(certfile=CERTFILE_PATH, keyfile=KEYFILE_PATH)
            server_socket = context.wrap_socket(server_socket, server_side=True)
            logger.info("SSL enabled")
        except FileNotFoundError:
            logger.warning(f"Certificate files not found. Running without SSL.")
            logger.warning(f"Expected certificate files at: {CERTFILE_PATH} and {KEYFILE_PATH}")
        except Exception as e:
            logger.warning(f"Failed to initialize SSL: {e}")
            logger.warning("Running without SSL")

        # Accept connections
        while True:
            client_socket, address = server_socket.accept()
            clients[client_socket] = address
            client_thread = threading.Thread(target=handle_client, args=(client_socket, address))
            client_thread.daemon = True
            client_thread.start()

    except KeyboardInterrupt:
        logger.info("Server shutting down.")
    except Exception as e:
        logger.error(f"Server error: {e}")
    finally:
        server_socket.close()

if __name__ == "__main__":
    main()
