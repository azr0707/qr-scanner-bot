import os
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Загружаем настройки из .env
from dotenv import load_dotenv
load_dotenv()

# Создаем подключение к БД
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///users.db')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Модель пользователя
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String)
    last_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    qr_data = Column(String, nullable=True)  # Данные из QR-кода
    scanned_at = Column(DateTime, default=datetime.now)
    created_at = Column(DateTime, default=datetime.now)

# Создаем таблицы
Base.metadata.create_all(bind=engine)

# Функция для получения сессии БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()