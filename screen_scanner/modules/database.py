"""
Veritabanı Modülü
Bu modül, SQLite veritabanı işlemlerini yönetir.
İşlem görüntülerinin bilgilerini saklar ve yönetir.
"""
import sqlite3
import os
import time
from modules.config import DATABASE_PATH

def ensure_dir_exists(file_path):
    """Dosya yolunun dizininin var olduğundan emin olur."""
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)

def initialize_database():
    """
    Veritabanını başlatır ve gerekli tabloları oluşturur.
    Eğer veritabanı yoksa yeni bir tane oluşturur.
    """
    ensure_dir_exists(DATABASE_PATH)
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # İşlem tablosunu oluştur
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        image_path TEXT NOT NULL,
        key_to_press TEXT NOT NULL,
        key_when_not_found TEXT,
        check_interval INTEGER,
        threshold REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active INTEGER DEFAULT 1
    )
    ''')
    
    # Log tablosunu oluştur
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER,
        action TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        details TEXT,
        FOREIGN KEY (task_id) REFERENCES tasks (id)
    )
    ''')
    
    conn.commit()
    conn.close()
    
    print("Veritabanı başarıyla başlatıldı.")

def add_default_task():
    """Varsayılan bir görev ekler."""
    from modules.config import DEFAULT_TEMPLATE_PATH, DEFAULT_KEY_TO_PRESS, DEFAULT_KEY_WHEN_NOT_FOUND, DEFAULT_CHECK_INTERVAL, DEFAULT_THRESHOLD
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Önce default task var mı kontrol et
    cursor.execute("SELECT COUNT(*) FROM tasks")
    count = cursor.fetchone()[0]
    
    if count == 0:
        cursor.execute('''
        INSERT INTO tasks (name, image_path, key_to_press, key_when_not_found, check_interval, threshold)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', ("Varsayılan İşlem", DEFAULT_TEMPLATE_PATH, DEFAULT_KEY_TO_PRESS, 
              DEFAULT_KEY_WHEN_NOT_FOUND, DEFAULT_CHECK_INTERVAL, DEFAULT_THRESHOLD))
        
        conn.commit()
        print("Varsayılan işlem eklendi.")
    
    conn.close()

def get_all_tasks():
    """Tüm işlemleri listeler."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM tasks WHERE is_active = 1 ORDER BY id")
    tasks = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return tasks

def get_task_by_id(task_id):
    """ID'ye göre işlem getirir."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    
    conn.close()
    return dict(task) if task else None

def add_task(name, image_path, key_to_press, key_when_not_found=None, check_interval=None, threshold=None):
    """Yeni bir işlem ekler."""
    from modules.config import DEFAULT_KEY_WHEN_NOT_FOUND, DEFAULT_CHECK_INTERVAL, DEFAULT_THRESHOLD
    
    if key_when_not_found is None:
        key_when_not_found = DEFAULT_KEY_WHEN_NOT_FOUND
    if check_interval is None:
        check_interval = DEFAULT_CHECK_INTERVAL
    if threshold is None:
        threshold = DEFAULT_THRESHOLD
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO tasks (name, image_path, key_to_press, key_when_not_found, check_interval, threshold)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (name, image_path, key_to_press, key_when_not_found, check_interval, threshold))
    
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return task_id

def update_task(task_id, name=None, image_path=None, key_to_press=None, key_when_not_found=None, check_interval=None, threshold=None):
    """İşlem bilgilerini günceller."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Mevcut görevi al
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    
    if not task:
        conn.close()
        return False
    
    # Güncellenecek alanları hazırla
    updates = []
    values = []
    
    if name is not None:
        updates.append("name = ?")
        values.append(name)
    if image_path is not None:
        updates.append("image_path = ?")
        values.append(image_path)
    if key_to_press is not None:
        updates.append("key_to_press = ?")
        values.append(key_to_press)
    if key_when_not_found is not None:
        updates.append("key_when_not_found = ?")
        values.append(key_when_not_found)
    if check_interval is not None:
        updates.append("check_interval = ?")
        values.append(check_interval)
    if threshold is not None:
        updates.append("threshold = ?")
        values.append(threshold)
    
    if updates:
        # ID'yi son parametre olarak ekle
        values.append(task_id)
        
        # Güncelleme sorgusu oluştur
        query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, values)
    
    conn.commit()
    conn.close()
    
    return True

def delete_task(task_id):
    """İşlemi siler (aktif olmayan olarak işaretler)."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("UPDATE tasks SET is_active = 0 WHERE id = ?", (task_id,))
    
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return success

def log_action(task_id, action, details=None):
    """Yapılan işlemi loglar."""
    from modules.config import ENABLE_LOGS
    
    if not ENABLE_LOGS:
        return
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO logs (task_id, action, details)
    VALUES (?, ?, ?)
    ''', (task_id, action, details))
    
    conn.commit()
    conn.close() 