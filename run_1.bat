@echo off
cd /d D:\beljar\freelance\reza\smart_door\sm3

echo 🔄 Aktifkan virtual environment...
call Scripts\activate

echo 🚀 Menjalankan Flask server...
start cmd /k python app.py

timeout /t 3

echo 📡 Menjalankan WebSocket client...
start cmd /k python client.py

echo ✅ Semua sudah berjalan!
pause