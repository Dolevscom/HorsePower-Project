#include <Wire.h>
#include <VL53L1X.h>

VL53L1X sensor;
const int buttonPin = 11; // Pin for the button
int buttonState = 0;

void setup() {
  pinMode(buttonPin, INPUT_PULLUP); // Set the button pin as input with internal pull-up
  Serial.begin(115200);
  Wire.begin();
  Wire.setClock(400000); // Use 400 kHz I2C

  sensor.setTimeout(500);
  if (!sensor.init()) {
    Serial.println("Failed to detect and initialize sensor!");
    while (1);
  }

  sensor.setDistanceMode(VL53L1X::Long);
  sensor.setMeasurementTimingBudget(50000);
  sensor.startContinuous(100);
  Serial.println("Setup complete. Starting loop...");
}

void loop() {
  buttonState = digitalRead(buttonPin);

  // Print button state for debugging
  // Serial.print("Button state: ");
  // Serial.println(buttonState);

  if (buttonState == LOW) { // Button is pressed (active low)
    Serial.println("SPACE"); // Send a keyword over Serial
    delay(100); // Debounce delay
  }

  sensor.read();
  // Serial.print("Sensor range (mm): ");
  Serial.println(sensor.ranging_data.range_mm);

  delay(100);
}
