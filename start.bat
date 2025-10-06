@echo off
echo Запуск веб-сервера для сканера QR-кодов...
start python web_server.py

timeout /t 3

echo Запуск бота...
python bot.py

pause