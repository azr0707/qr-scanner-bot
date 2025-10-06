import http.server
import socketserver
import os

# Пробуем разные порты
PORTS = [8081, 8082, 8083, 8088, 8089]

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.path = '/qr_scanner.html'
        return super().do_GET()

print("=== ЗАПУСК ВЕБ-СЕРВЕРА ===")

for PORT in PORTS:
    try:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print(f"=== ВЕБ-СЕРВЕР ЗАПУЩЕН ===")
            print(f"Адрес: http://localhost:{PORT}")
            print("Сканер QR-кодов готов к работе!")
            print("Не закрывайте это окно!")
            httpd.serve_forever()
        break
    except OSError:
        print(f"Порт {PORT} занят, пробуем следующий...")
        continue