import serial
import time
from pynput.keyboard import Controller

ser = serial.Serial('COM5 ', 115200)
keyboard = Controller()

while True:
    if ser.in_waiting > 0:
        line = ser.readline().decode('utf-8').strip()
        print(f"Received: {line}")
        if line == "SPACE":
            keyboard.press(' ')
            keyboard.release(' ')
            time.sleep(0.2)  # Add a small delay to prevent multiple rapid key presses
