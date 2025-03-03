
#include <ESP8266WiFi.h>
#include <WiFiUdp.h>

// Replace with your WiFi credentials
char ssid[] = "prateeksha";
char pass[] = "prateeksha0209";

const unsigned int localPort = 2910; // Local port for UDP
WiFiUDP udp;
IPAddress broadcastIP(255, 255, 255, 255); // Broadcast IP for message exchange

// Sensor variables
int lightReading;
int ledPin2 = D8; // External LED
bool isMaster = false;
unsigned long lastPacketTime = 0; // Timestamp for last packet received/sent
const unsigned long silenceThreshold = 100; // Silence threshold in ms
unsigned long masterDeterminationStart; // Track master determination time

// LED Bar Graph Pins
const int barGraphPins[] = {D0, D1, D2, D3, D4}; // Adjust based on available pins
const int numBarGraphLEDs = sizeof(barGraphPins) / sizeof(barGraphPins[0]);

void setup() {
  Serial.begin(9600);
  pinMode(LED_BUILTIN, OUTPUT); // Onboard LED for Master
  pinMode(ledPin2, OUTPUT);     // External LED for brightness

  // Initialize LED bar graph pins
  for (int i = 0; i < numBarGraphLEDs; i++) {
    pinMode(barGraphPins[i], OUTPUT);
    digitalWrite(barGraphPins[i], LOW); // Turn off all LEDs initially
  }

  // Connect to WiFi
  Serial.println("Connecting to WiFi...");
  WiFi.begin(ssid, pass);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());

  // Start UDP
  udp.begin(localPort);
  Serial.print("Listening on port ");
  Serial.println(localPort);

  masterDeterminationStart = millis();
}

void loop() {
  // Read the light sensor
  lightReading = analogRead(A0);
  Serial.print("Light reading: ");
  Serial.println(lightReading);

  // Adjust brightness of external LED using PWM
  adjustLEDBrightness(lightReading);

  // Update LED bar graph
  updateLEDBarGraph(lightReading);

  // Check for incoming packets
  checkForPackets();

  // Check network silence and broadcast readings
  if (millis() - lastPacketTime > silenceThreshold) {
    isMaster = true; // Default to master if no higher reading received
    broadcastReading(lightReading);
  }

  // Determine Master
  if (millis() - lastPacketTime < silenceThreshold) {
    if (isMaster) {
      digitalWrite(LED_BUILTIN, LOW); // Turn on onboard LED for Master
      Serial.println("I am the Master");
    } else {
      digitalWrite(LED_BUILTIN, HIGH); // Turn off onboard LED for non-Master
      Serial.println("I am a Slave");
    }
  }

  delay(100); // Prevent overwhelming the network
}

void broadcastReading(int reading) {
  byte packet[4];
  packet[0] = 0x01; // Packet type (light reading)
  packet[1] = (reading >> 8) & 0xFF; // High byte
  packet[2] = reading & 0xFF;        // Low byte
  packet[3] = 0xFF;                  // End byte

  udp.beginPacket(broadcastIP, localPort);
  udp.write(packet, sizeof(packet));
  udp.endPacket();

  lastPacketTime = millis(); // Update the last packet sent timestamp
}

void checkForPackets() {
  int packetSize = udp.parsePacket();
  if (packetSize) {
    byte buffer[4];
    udp.read(buffer, packetSize);

    if (buffer[0] == 0x01) { // Light reading packet
      int receivedReading = (buffer[1] << 8) | buffer[2];
      Serial.print("Received reading: ");
      Serial.println(receivedReading);

      // Determine if this device should remain Master
      if (receivedReading > lightReading) {
        isMaster = false;
      }
    }

    lastPacketTime = millis(); // Update the last packet received timestamp
  }
}

void adjustLEDBrightness(int reading) {
  // Map light reading (0-1023) to PWM brightness (0-255)
  int brightness = map(reading, 0, 1023, 0, 255);
  analogWrite(ledPin2, brightness);
}

void updateLEDBarGraph(int reading) {
  // Map light reading (0-1023) to the number of LEDs to light up (0 to numBarGraphLEDs)
  int numLitLEDs = map(reading, 0, 50, 0, numBarGraphLEDs);

  Serial.print("Number of LEDs to light up: ");
  Serial.println(numLitLEDs);

  // Turn on the appropriate number of LEDs
  for (int i = 0; i < numBarGraphLEDs; i++) {
    if (i < numLitLEDs) {
      digitalWrite(barGraphPins[i], HIGH);
      Serial.print("Turning ON LED at pin: ");
      Serial.println(barGraphPins[i]);
    } else {
      digitalWrite(barGraphPins[i], LOW);
      Serial.print("Turning OFF LED at pin: ");
      Serial.println(barGraphPins[i]);
    }
  }
}
