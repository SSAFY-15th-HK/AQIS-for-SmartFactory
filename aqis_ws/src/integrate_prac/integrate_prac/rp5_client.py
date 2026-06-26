# -*- coding: utf-8 -*-
import socket
import time
import threading

# Define the server host and port
HOST = '127.0.0.1'
PORT = 65432

def connect_to_server():
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((HOST, PORT))

            print(f"Connected to {HOST}:{PORT}")
            return s  # Return the socket object once connected
        except socket.error as e:
            print(f"Connection failed: {e}. Retrying in 5 seconds...")
            s.close()
            time.sleep(5)

try:
    while True:
        # Try to connect to the server
        s = connect_to_server()

        while True:
            try:
                # Wait for a message (command) from the server
                data = s.recv(1024)
                if not data:
                    break

                command = data.decode('utf-8')

                # Handle the command received from the server
                if command == '1':
                    print('command 1 recieved')
                elif command == '2':
                    print('command 2 recieved')
                elif command == '3':
                    print('command 3 recieved')
                elif command == '4':
                    print('command 4 recieved')
                else:
                    print('Unknown command recieved')    

            except socket.error as e:
              print(f"Socket error: {e}. Reconnecting...")
              break  # Exit inner loop and reconnect
    
        # Close the socket after disconnection
        s.close()

except KeyboardInterrupt:
    print("Program terminated")
except Exception as e:
    print(f"An error occurred: {e}")
finally:
    # Stop motor and release GPIO lines
    print("Resources released and motor stopped.")