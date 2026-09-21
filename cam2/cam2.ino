#include "esp_camera.h"
#include <WiFi.h>
#include <WebSocketsServer.h>

const char* ssid = "0987654321";
const char* password = "indonesia";


WebSocketsServer webSocket = WebSocketsServer(81);

void showIP()
{
  Serial.print("IP Camera: ");
  Serial.println(WiFi.localIP());
}

void startCamera()
{
  camera_config_t config;

  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;

  config.pin_d0 = 5;
  config.pin_d1 = 18;
  config.pin_d2 = 19;
  config.pin_d3 = 21;
  config.pin_d4 = 36;
  config.pin_d5 = 39;
  config.pin_d6 = 34;
  config.pin_d7 = 35;

  config.pin_xclk = 0;
  config.pin_pclk = 22;
  config.pin_vsync = 25;
  config.pin_href = 23;

  config.pin_sccb_sda = 26;
  config.pin_sccb_scl = 27;

  config.pin_pwdn = 32;
  config.pin_reset = -1;

  config.xclk_freq_hz = 20000000;

  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_QVGA;
  config.jpeg_quality = 12;
  config.fb_count = 1;

  esp_camera_init(&config);
}

void setup()
{
  Serial.begin(115200);

  Serial.println("Connecting WiFi...");

  WiFi.begin(ssid,password);

  while(WiFi.status()!=WL_CONNECTED)
  {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("WiFi Connected");

  showIP();

  startCamera();

  webSocket.begin();

  Serial.println("WebSocket started");
  Serial.println("Ketik 'ip' di Serial Monitor untuk melihat IP");
}

void loop()
{
  webSocket.loop();

  // streaming kamera
  camera_fb_t * fb = esp_camera_fb_get();

  if(fb)
  {
    webSocket.broadcastBIN(fb->buf, fb->len);
    esp_camera_fb_return(fb);
  }

  // cek perintah serial
  if(Serial.available())
  {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if(cmd == "ip")
    {
      showIP();
    }
  }

  delay(50);
}