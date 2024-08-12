#include <Wire.h>
#include <VL53L0X.h>

VL53L0X sensor;

void setup() {
  Serial.begin(9600);
  Wire.begin();

  // Add a delay to allow the sensor to fully power up and stabilize
  delay(100);  // 100 milliseconds delay

  // Attempt to initialize the sensor
  if (!sensor.init()) {
    Serial.println("Failed to initialize sensor! Check connections and power.");
    while (1); // Halt if sensor initialization fails
  }

  // Set sensor timeout to handle potential delays in communication
  sensor.setTimeout(500);

  // Set the measurement timing budget (in microseconds)
  sensor.setMeasurementTimingBudget(50000); // 50 ms timing budget for stable readings

  Serial.println("Sensor initialized successfully!");
}

void loop() {
  // Take a reading
  uint16_t distance = sensor.readRangeSingleMillimeters();

  // Check for a timeout or an out-of-range value
  if (sensor.timeoutOccurred()) {
    Serial.println("Sensor timeout!");
  } else {
    Serial.print("Distance: ");
    Serial.print(distance);
    Serial.println(" mm");
  }

  delay(100);  // Delay to give the sensor time between readings
}
