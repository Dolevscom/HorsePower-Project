//#include "Adafruit_VL53L1X.h"//
#include "SparkFun_VL53L1X.h" //Click here to get the library: http://librarymanager/All#SparkFun_VL53L1X
#include "TimerOne.h"//Click here to get the library: http://librarymanager/All#TimerOne
//#include <TimerOne.h>

#define IRQ_PIN 2
#define XSHUT_PIN 3
#define bufferSize 20
#define floor_distance 300
#define floor_distance_thresh 10
#define consecutive_samples 3  // Number of consecutive samples to check
#define time_intvl 5000  // 5 ms in us
#define time_intvl_measure_win 7  // n*5 ms
#define time_intvl_win 10  // n*5 ms
#define measurement_period 3000000  // 10 seconds in milliseconds
#define minMeasurementsCnt 3

#define wait4buff_state 0
#define start_state 1
#define min_state 2 
#define post_time_state 3 
#define return2start_state 4 


uint8_t current_state = 0;
uint8_t return2start_state_CNT = 0;

SFEVL53L1X vl53;//(Wire, XSHUT_PIN, IRQ_PIN);
//Adafruit_VL53L1X vl53 = Adafruit_VL53L1X(XSHUT_PIN, IRQ_PIN);

unsigned long currentTime = 0;
unsigned long elapsedTime = 0;
unsigned long thresholdEventCount = 0;
unsigned long thresholdEventTime = 0;
volatile bool readSensorFlag = false;
unsigned long lastReadTime = 0;
unsigned long preThresholdTime = 0;
unsigned long thresholdTime = 0;
int16_t buffer[bufferSize];
size_t buff_indx = 0;
size_t valid_samples = 0;
uint8_t time_intvl_CNT = 0;
uint8_t Data_Ready = 1;
//unsigned long elapsedTime[3];

struct Measurement {
  int16_t absolute_distance;
  //int16_t relative_distance;
  unsigned long eventCount;
};

Measurement minMeasurements[minMeasurementsCnt+1];
size_t minMeasurementsIndex = 0;
bool thresholdMet = false;
size_t minMeasurement = 5000; //5m

/////////////////////////////////////////////////////////////////////
void setup() {
  Serial.begin(115200);
  Serial.println("Setup started!");  // Add this line for debugging

  while (!Serial) delay(10);

  Serial.println(F(__FILE__ " " __DATE__ " " __TIME__));
  Serial.println("START");
  Serial.println(F(" VL53L1X sensor "));

  Wire.begin();
  Wire.setClock(400000);  // Set I2C clock speed to 400 kHz

  if (vl53.begin() != 0) {
    Serial.print(F("Error on init of VL sensor: "));
    while (1) delay(10);
  }
  Serial.println(F("VL53L1X sensor OK!"));

  Serial.print(F("Sensor ID: 0x"));
  Serial.println(vl53.getSensorID(), HEX);


  // Valid timing budgets: 15, 20, 33, 50, 100, 200 and 500ms!
  vl53.setTimingBudgetInMs(33);
  Serial.print(F("Timing budget (ms): "));
  delay(10);
  Serial.println(vl53.getTimingBudgetInMs());
  
  for (minMeasurementsIndex = 0; minMeasurementsIndex < minMeasurementsCnt+1 ; minMeasurementsIndex++) {
    minMeasurements[minMeasurementsIndex].absolute_distance = 5000;
    minMeasurements[minMeasurementsIndex].eventCount = 0;//thresholdEventCount;
  }  
  current_state = wait4buff_state;

  // Set up Timer1 to trigger every 50ms
  Timer1.initialize(time_intvl); // 50ms in microseconds
  Timer1.attachInterrupt(timerISR);
}

void loop() {
  if (readSensorFlag) {
    readSensorFlag = false;
    time_intvl_CNT = (time_intvl_CNT + 1) % time_intvl_win;
    readSensor();
  }
}

void readSensor() {
  int16_t distance;
  currentTime = micros();
  elapsedTime = currentTime - lastReadTime;     
  //Serial.print(F("time_intvl_CNT = "));Serial.println(time_intvl_CNT);
  if (time_intvl_CNT == 0) {
    //Serial.println(F("*time_intvl_CNT == 0"));
    vl53.startRanging();
  }
  else if (time_intvl_CNT == time_intvl_measure_win){
    //Serial.println(F("**time_intvl_CNT == time_intvl_measure_win"));
    if (!vl53.checkForDataReady())
    {
      Data_Ready = 1;
    }
    else{
      Data_Ready = 0;   
    }
  }
  else if (time_intvl_CNT >= time_intvl_win-1){
    //Serial.println(F("***time_intvl_CNT == time_intvl_win")); 
    lastReadTime = currentTime;
    // New measurement available
    distance = vl53.getDistance();
    byte rangeStatus = vl53.getRangeStatus();  
    vl53.clearInterrupt();    // Data is read out, time for another reading

    if (distance == -1) {
      // Something went wrong
      Serial.print(F("Couldn't get distance: "));
      Serial.println(rangeStatus);
      return;
    } 
    else 
    {
      // Add new sample to the circular buffer
      buffer[buff_indx] = distance;
      buff_indx = (buff_indx + 1) % bufferSize;
      if (valid_samples < bufferSize) {
        valid_samples++;
        current_state = wait4buff_state;
      }
      else if (current_state == wait4buff_state) {
        current_state = start_state;
      }
        // #define wait4buff_state 0
        // #define start_state 1
        // #define min_state 2 
        // #define post_time_state 3 
        // #define return2start_state 4  
      switch(current_state) {

        case return2start_state:
          //Serial.println("current_state == return2start_state ");

          if (buffer[buff_indx] > (floor_distance - floor_distance_thresh)) {
            return2start_state_CNT++;
          }
          else if (return2start_state_CNT > 0) {
            return2start_state_CNT--;
          }
          if (return2start_state_CNT > consecutive_samples){
            current_state = wait4buff_state;
          }
          //while(1) delay(10);
        break;
                
        case wait4buff_state:
          thresholdEventCount = 0;      
          for (minMeasurementsIndex = 0; minMeasurementsIndex < minMeasurementsCnt+1 ; minMeasurementsIndex++) {
            minMeasurements[minMeasurementsIndex].absolute_distance = 5000;
            minMeasurements[minMeasurementsIndex].eventCount = thresholdEventCount;
          } 
          //Serial.println("current_state == wait4buff_state ");
      
          break;

        case start_state:        
          //Serial.println("current_state == start_state ");
          // Check for three consecutive samples smaller than floor_distance
          current_state = min_state;  
          for (size_t i = 0; i < consecutive_samples; i++) {
            size_t index = (buff_indx + bufferSize - 1 - i) % bufferSize;
            if (buffer[index] >= (floor_distance - floor_distance_thresh)) {
              current_state = start_state;
              break;
            }
          }   
          if (current_state == min_state) {
            minMeasurements[0].absolute_distance = distance;
            minMeasurements[0].eventCount = 0;//thresholdEventCount;
            thresholdEventCount = 3*time_intvl; // in uSec
            //Serial.print("*** start "); Serial.print(minMeasurements[0].absolute_distance);Serial.print(", ");Serial.println(minMeasurements[0].eventCount);
          }
          break;

        case min_state: 
          //Serial.println("current_state == min_state ");
          thresholdEventCount = thresholdEventCount + elapsedTime;;
          // After threshold is met, record the three minimal measurements with their time tags
          if (distance < minMeasurements[1].absolute_distance){
            minMeasurements[3].absolute_distance = minMeasurements[2].absolute_distance;
            minMeasurements[3].eventCount = minMeasurements[2].eventCount;
            minMeasurements[2].absolute_distance = minMeasurements[1].absolute_distance;
            minMeasurements[2].eventCount = minMeasurements[1].eventCount;             
            minMeasurements[1].absolute_distance = distance;
            minMeasurements[1].eventCount = thresholdEventCount;          
          } 
          // Break the loop after the measurement period
          if (thresholdEventCount >= measurement_period) {
            current_state = post_time_state;
          }
        break;

        case post_time_state: 
          Serial.println("current_state == post_time_state ");
          Serial.println("Measurement period ended.");

          // Print the three minimal measurements with their time tags
          Serial.println(F("Three minimal measurements:"));
          for (size_t i = 0; i < 4; i++) {
            Serial.print("Absolute Distance: ");
            Serial.print(minMeasurements[i].absolute_distance);
            Serial.print(" mm, Relative Distance: ");
            Serial.print(floor_distance - minMeasurements[i].absolute_distance);
            Serial.print(" mm, Time: ");
            Serial.print(minMeasurements[i].eventCount);
            Serial.println(" us");
          }
          //Find Max travel
          uint8_t largest_INDX = 1;
          if (minMeasurements[2].absolute_distance >= minMeasurements[1].absolute_distance){
            if (minMeasurements[3].absolute_distance >= minMeasurements[1].absolute_distance){
              largest_INDX = 1;
            }
            else{
              largest_INDX = 3;
            }
          }
          else if(minMeasurements[3].absolute_distance >= minMeasurements[2].absolute_distance){
            largest_INDX = 2;
          }
          else{
            largest_INDX = 3;
          }
          uint16_t max_travel = floor_distance - minMeasurements[largest_INDX].absolute_distance;

          Serial.print("max_travel was ");
          Serial.print(max_travel);
          Serial.print(" mm, in ");
          Serial.print(minMeasurements[largest_INDX].eventCount/1000);
          Serial.println(" mSec.");        
          Serial.println("*****************************************************************");

          return2start_state_CNT = 0;
          current_state = return2start_state;
        break;

        default:
          current_state = wait4buff_state;
      }
    
      // // Print buffer contents
      // Serial.print(F("Buffer: "));
      // for (size_t i = 0; i < bufferSize; i++) {
      //   Serial.print(buffer[i]);
      //   Serial.print(" ");
      // }
      // Serial.println();

    }

  }

}

void timerISR() {
  readSensorFlag = true;
  //Serial.println(micros());
}
