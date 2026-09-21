#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// =====================================================
// WIFI CONFIG
// =====================================================
const char* ssid = "0987654321";
const char* password = "indonesia";

// =====================================================
// SERVER API
// =====================================================
const char* serverName = "http://10.103.46.215:5000/api/status";
const char* lockApi    = "http://10.103.46.215:5000/api/kunci-pintu";
const char* openApi    = "http://10.103.46.215:5000/api/buka-pintu";

// =====================================================
// LCD
// =====================================================
LiquidCrystal_I2C lcd(0x27, 16, 2);

// =====================================================
// PIN CONFIG
// =====================================================
#define RELAY_PIN 2
#define LED_PIN   2

const int buttonPin = 13;

// =====================================================
// RELAY STATE
// Relay Active LOW
// =====================================================
#define RELAY_LOCKED   HIGH
#define RELAY_UNLOCKED LOW

TaskHandle_t Task2;

// =====================================================
// BUTTON
// =====================================================
bool buttonState = HIGH;
bool lastReading = HIGH;

unsigned long lastDebounceTime = 0;
const unsigned long debounceDelay = 50;

// =====================================================
// STATUS TRACKING
// =====================================================
String lastAction = "";
String lastStatus = "";
String lastUser   = "";

volatile bool isLocked = true;

// =====================================================
// TIMER
// =====================================================
unsigned long lastStatusCheck = 0;
const unsigned long intervalStatus = 3000;

// =====================================================
// AUTO LOCK
// =====================================================
volatile unsigned long unlockTime = 0;
const unsigned long autoLockDelay = 10000;

// =====================================================
// API LOCK
// =====================================================
void hitLockApi() {

  HTTPClient http;

  http.begin(lockApi);
  http.setTimeout(3000);

  int responseCode = http.GET();

  Serial.print("LOCK API CODE: ");
  Serial.println(responseCode);

  if (responseCode > 0) {

    String payload = http.getString();

    Serial.println(payload);
  }

  http.end();
}

// =====================================================
// API OPEN
// =====================================================
void hitOpenApi() {

  HTTPClient http;

  http.begin(openApi);
  http.setTimeout(3000);

  int responseCode = http.GET();

  Serial.print("OPEN API CODE: ");
  Serial.println(responseCode);

  if (responseCode > 0) {

    String payload = http.getString();

    Serial.println(payload);
  }

  http.end();
}

// =====================================================
// AUTO LOCK
// =====================================================
void handleAutoLock() {

  if (!isLocked) {

    if (millis() - unlockTime >= autoLockDelay) {

      Serial.println("AUTO LOCK");

      hitLockApi();

      isLocked = true;

      digitalWrite(RELAY_PIN, RELAY_LOCKED);
      digitalWrite(LED_PIN, LOW);

      lcd.clear();

      lcd.setCursor(0, 0);
      lcd.print("Door Locked");

      lcd.setCursor(0, 1);
      lcd.print("Auto Lock");
    }
  }
}

// =====================================================
// BUTTON
// =====================================================
void handleButton() {

  int reading = digitalRead(buttonPin);

  Serial.print("Button: ");
  Serial.println(reading);

  // DETECT CHANGE
  if (reading != lastReading) {

    lastDebounceTime = millis();
  }

  // DEBOUNCE
  if ((millis() - lastDebounceTime) > debounceDelay) {

    // STATE CHANGED
    if (reading != buttonState) {

      buttonState = reading;

      // BUTTON PRESSED
      if (buttonState == LOW) {

        Serial.println("BUTTON PRESSED");

        lcd.clear();

        lcd.setCursor(0, 0);
        lcd.print("Opening Door");

        lcd.setCursor(0, 1);
        lcd.print("Please Wait");

        hitOpenApi();
      }
    }
  }

  lastReading = reading;
}

// =====================================================
// CHECK SERVER STATUS
// =====================================================
void checkServerStatus() {

  HTTPClient http;

  http.begin(serverName);
  http.setTimeout(3000);

  int httpResponseCode = http.GET();

  if (httpResponseCode > 0) {

    String payload = http.getString();

    Serial.println(payload);

    StaticJsonDocument<512> doc;

    DeserializationError error = deserializeJson(doc, payload);

    if (!error) {

      // =================================================
      // JSON DATA
      // =================================================
      String action = doc["action"] | "";
      String status = doc["status"] | "";
      String user   = doc["user"] | "";

      // =================================================
      // RELAY CONTROL
      // =================================================
      if (action != lastAction) {

        // =========================
        // UNLOCK
        // =========================
        if (action == "unlock") {

          Serial.println("UNLOCK");

           digitalWrite(RELAY_PIN, RELAY_LOCKED);
          digitalWrite(LED_PIN, LOW);
          isLocked = false;

          unlockTime = millis();
        }

        // =========================
        // LOCK
        // =========================
        else if (action == "lock") {

          Serial.println("LOCK");
  digitalWrite(RELAY_PIN, RELAY_UNLOCKED);
          digitalWrite(LED_PIN, HIGH);

       

          isLocked = true;
        }
      }

      // =================================================
      // LCD UPDATE
      // =================================================
      if (user != lastUser ||
          status != lastStatus ||
          action != lastAction) {

        lcd.clear();

        // =============================================
        // LOCKED STATE
        // =============================================
        if (isLocked && status == "schedule_denied") {

          lcd.setCursor(0, 0);
          lcd.print("Tidak");

          lcd.setCursor(0, 1);
          lcd.print("Terjadwal");
        }

        else if (isLocked && status == "unknown_face") {

          lcd.setCursor(0, 0);
          lcd.print("Wajah Tidak");

          lcd.setCursor(0, 1);
          lcd.print("Dikenali");
        }

        else if (isLocked) {

          lcd.setCursor(0, 0);
          lcd.print("Menunggu...");

          lcd.setCursor(0, 1);
          lcd.print("Scan Wajah");
        }

        // =============================================
        // UNLOCKED STATE
        // =============================================
        else {

          lcd.setCursor(0, 0);

          String displayName = user;

          // LIMIT 16 CHAR
          if (displayName.length() > 16) {

            displayName = displayName.substring(0, 16);
          }

          lcd.print(displayName);

          lcd.setCursor(0, 1);

          if (status == "granted") {

            lcd.print("ACCESS OK");
          }

          else if (status == "denied" ||
                   status == "schedule_denied") {

            lcd.print("ACCESS FAIL");
          }

          else {

            lcd.print("WAITING...");
          }
        }

        // SAVE LAST STATE
        lastUser   = user;
        lastStatus = status;
        lastAction = action;
      }

    } else {

      Serial.println("JSON PARSE FAILED");
    }

  } else {

    Serial.print("HTTP ERROR: ");
    Serial.println(httpResponseCode);

    lcd.clear();

    lcd.setCursor(0, 0);
    lcd.print("Server Error");

    lcd.setCursor(0, 1);
    lcd.print("Check Network");
  }

  http.end();
}

// =====================================================
// TASK
// =====================================================
void Task2code(void* pvParameters) {

  for (;;) {

    handleButton();

    vTaskDelay(50 / portTICK_PERIOD_MS);
  }
}

// =====================================================
// SETUP
// =====================================================
void setup() {

  Serial.begin(115200);

  // ===================================================
  // PIN MODE
  // ===================================================
  pinMode(RELAY_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);

  pinMode(buttonPin, INPUT_PULLUP);

  // ===================================================
  // DEFAULT LOCK
  // ===================================================
  digitalWrite(RELAY_PIN, RELAY_LOCKED);
  digitalWrite(LED_PIN, LOW);

  // ===================================================
  // LCD INIT
  // ===================================================
  lcd.init();
  lcd.backlight();

  // ===================================================
  // SPLASH SCREEN
  // ===================================================
  lcd.clear();

  lcd.setCursor(0, 0);
  lcd.print("Face Recognition");

  lcd.setCursor(0, 1);
  lcd.print("By Reza Hifzar");

  delay(3000);

  // ===================================================
  // CONNECT WIFI
  // ===================================================
  lcd.clear();

  lcd.setCursor(0, 0);
  lcd.print("Connecting WiFi");

  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {

    delay(500);

    Serial.print(".");
  }

  Serial.println();
  Serial.println("WIFI CONNECTED");

  Serial.println(WiFi.localIP());

  lcd.clear();

  lcd.setCursor(0, 0);
  lcd.print("WiFi Connected");

  lcd.setCursor(0, 1);
  lcd.print(WiFi.localIP());

  delay(2000);

  // ===================================================
  // BUTTON TASK
  // ===================================================
  xTaskCreatePinnedToCore(
    Task2code,
    "Task2",
    4096,
    NULL,
    1,
    &Task2,
    1
  );
}

// =====================================================
// LOOP
// =====================================================
void loop() {

  // ===================================================
  // WIFI RECONNECT
  // ===================================================
  if (WiFi.status() != WL_CONNECTED) {

    Serial.println("WIFI DISCONNECTED");

    lcd.clear();

    lcd.setCursor(0, 0);
    lcd.print("Reconnect WiFi");

    WiFi.begin(ssid, password);

    delay(1000);

    return;
  }

  // ===================================================
  // CHECK SERVER STATUS
  // ===================================================
  if (millis() - lastStatusCheck >= intervalStatus) {

    checkServerStatus();

    lastStatusCheck = millis();
  }

  // ===================================================
  // AUTO LOCK
  // ===================================================
  handleAutoLock();
}