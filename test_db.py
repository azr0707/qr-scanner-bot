from database import SessionLocal, User
from datetime import datetime

# Создаем сессию базы данных
db = SessionLocal()

try:
    # Тестовый пользователь
    test_user = User(
        user_id=123456789,
        username="test_user",
        first_name="Test",
        last_name="User", 
        qr_data="test_qr_data_12345"
    )
    
    # Добавляем и сохраняем
    db.add(test_user)
    db.commit()
    
    print("✅ Тестовый пользователь успешно сохранен в базу данных!")
    print(f"📊 ID пользователя: {test_user.user_id}")
    print(f"📝 Имя: {test_user.first_name}")
    print(f"🔢 QR данные: {test_user.qr_data}")
    
except Exception as e:
    print(f"❌ Ошибка: {e}")
finally:
    db.close()