#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Ekran Tarayıcı (Screen Scanner) Ana Programı

Bu program, ekranda belirli bir görüntüyü arayıp bulunan ya da bulunmayan durumlarda
belirlenen klavye tuşlarına otomatik olarak basabilen bir otomasyon aracıdır.
Kullanıcı, farklı tarama görevleri tanımlayabilir, düzenleyebilir ve çalıştırabilir.

Özellikler:
- Ekranda belirli bir görüntüyü arama ve bulma
- Görüntü bulunduğunda veya bulunamadığında belirlenen tuşlara basma
- Çoklu tarama görevlerini yönetme ve kaydetme
- Veritabanında görev bilgilerini ve logları saklama

Modüller:
- modules.scanner: Tarama işlemlerini gerçekleştirir
- modules.ui: Kullanıcı arayüzü fonksiyonlarını içerir
- modules.database: Veritabanı işlemlerini yönetir
- modules.config: Program genelindeki ayarları içerir
"""

import os
import re
import sys
import time
from pathlib import Path

# Modüllerin içe aktarılması
from modules.database import (add_task, delete_task, get_all_tasks,
                             get_task_by_id, initialize_database, update_task)
from modules.scanner import run_scanner
from modules.ui import display_header, display_menu, print_task_info, select_screen_region

# Program süreci içinde karşılaşılan hataları yakalama ve işleme fonksiyonu
def handle_error(error_message, exit_program=False):
    """
    Hata mesajlarını ekrana yazdırır ve gerekirse programı sonlandırır.
    
    Args:
        error_message (str): Gösterilecek hata mesajı
        exit_program (bool): True ise program sonlandırılır, False ise devam eder
    """
    print(f"\n[HATA] {error_message}")
    if exit_program:
        print("Program sonlandırılıyor...")
        sys.exit(1)
    input("\nDevam etmek için ENTER tuşuna basın...")

# Klasör varlığını kontrol etme ve yoksa oluşturma fonksiyonu
def ensure_directory_exists(directory_path):
    """
    Belirtilen klasörün varlığını kontrol eder, yoksa oluşturur.
    
    Args:
        directory_path (str): Kontrol edilecek klasör yolu
    
    Returns:
        bool: Klasörün varlığı veya başarıyla oluşturulması durumunda True, aksi halde False
    """
    try:
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)
            print(f"'{directory_path}' klasörü oluşturuldu.")
        return True
    except Exception as e:
        handle_error(f"'{directory_path}' klasörü oluşturulurken hata oluştu: {str(e)}")
        return False

# Uygulamayı başlatma ve gerekli ön hazırlıkları yapma fonksiyonu
def initialize_app():
    """
    Uygulamayı başlatır ve gerekli ön hazırlıkları yapar:
    - Gerekli klasörlerin varlığını kontrol eder
    - Veritabanını başlatır
    - Genel program başlangıç işlemlerini gerçekleştirir
    
    Returns:
        bool: Başlatma işlemi başarılı ise True, değilse False
    """
    print("Uygulama başlatılıyor...")
    
    # Gerekli klasörlerin varlığını kontrol et
    if not ensure_directory_exists("data"):
        return False
    if not ensure_directory_exists("images"):
        return False
    
    # Veritabanını başlat
    try:
        initialize_database()
        print("Veritabanı başarıyla başlatıldı.")
        return True
    except Exception as e:
        handle_error(f"Veritabanı başlatılırken hata oluştu: {str(e)}")
        return False

# Yeni tarama işlemi başlatma fonksiyonu
def start_new_scan():
    """
    Kullanıcının kayıtlı görevler arasından seçim yapmasını sağlar
    ve seçilen görevle yeni bir tarama işlemi başlatır.
    """
    # Kayıtlı görevleri getir
    tasks = get_all_tasks()
    
    if not tasks:
        handle_error("Henüz kayıtlı görev bulunmuyor. Önce bir görev ekleyin.")
        return
    
    # Görevleri listele
    print("\n=== KAYITLI GÖREVLER ===")
    for i, task in enumerate(tasks, 1):
        print(f"{i}. {task['name']}")
    
    # Görev seçimi
    try:
        selection = int(input("\nBaşlatmak istediğiniz görevin numarasını girin (0 = İptal): "))
        
        if selection == 0:
            return
        
        if 1 <= selection <= len(tasks):
            selected_task = tasks[selection - 1]
            print(f"\n'{selected_task['name']}' görevi seçildi.")
            
            # Görev bilgilerini göster
            print_task_info(selected_task)
            
            # Taranacak ekran bölgesini seç
            print("\nTaranacak ekran bölgesini seçin...")
            print("1. Sol üst köşeye gelin ve SPACE tuşuna basın")
            print("2. Sağ alt köşeye gelin ve SPACE tuşuna basın")
            print("İptal etmek için ESC tuşuna basın")
            
            region = select_screen_region()
            if region:
                print(f"Seçilen bölge: {region}")
                
                # Tarama işlemini başlat
                print("\nTarama başlatılıyor...")
                print("Durdurmak için 'q' tuşuna basın.")
                time.sleep(2)  # Kullanıcıya hazırlanması için süre ver
                
                run_scanner(selected_task, region)
            else:
                print("Bölge seçimi iptal edildi.")
        else:
            handle_error("Geçersiz görev numarası.")
    except ValueError:
        handle_error("Lütfen bir sayı girin.")
    except Exception as e:
        handle_error(f"Tarama başlatılırken hata oluştu: {str(e)}")

# Tüm görevleri listeleme fonksiyonu
def list_all_tasks():
    """
    Veritabanındaki tüm görevleri listeler ve kullanıcının
    detaylı bilgi görmek istediği görevi seçmesini sağlar.
    """
    # Görevleri getir
    tasks = get_all_tasks()
    
    if not tasks:
        print("\nHenüz kayıtlı görev bulunmuyor.")
        return
    
    # Görevleri listele
    print("\n=== KAYITLI GÖREVLER ===")
    for i, task in enumerate(tasks, 1):
        print(f"{i}. {task['name']}")
    
    # Görev detayı görüntüleme
    try:
        selection = int(input("\nDetaylarını görmek istediğiniz görevin numarasını girin (0 = İptal): "))
        
        if selection == 0:
            return
        
        if 1 <= selection <= len(tasks):
            selected_task = tasks[selection - 1]
            print(f"\n'{selected_task['name']}' görevi detayları:")
            print_task_info(selected_task)
            input("\nAna menüye dönmek için ENTER tuşuna basın...")
        else:
            handle_error("Geçersiz görev numarası.")
    except ValueError:
        handle_error("Lütfen bir sayı girin.")

# Yeni görev ekleme fonksiyonu
def add_new_task():
    """
    Kullanıcıdan yeni görev bilgilerini alır ve veritabanına kaydeder.
    Görüntü dosyası yolu, tuş isimleri, kontrol aralığı ve eşik değeri gibi
    parametreleri kullanıcıdan alarak bir görev oluşturur.
    """
    print("\n=== YENİ GÖREV EKLEME ===")
    
    try:
        # Görev adı
        name = input("Görev adı: ")
        if not name.strip():
            handle_error("Görev adı boş olamaz.")
            return
        
        # Görüntü dosyası
        print("\nAranacak görüntü dosyası (images/ klasöründe olmalı):")
        image_files = [f for f in os.listdir("images") if os.path.isfile(os.path.join("images", f))]
        
        if not image_files:
            handle_error("'images/' klasöründe görüntü dosyası bulunamadı. Önce bir görüntü ekleyin.")
            return
        
        print("\nMevcut görüntüler:")
        for i, img in enumerate(image_files, 1):
            print(f"{i}. {img}")
        
        image_selection = int(input("\nSeçiminiz (0 = Yeni dosya yolu gir): "))
        
        if image_selection == 0:
            image_path = input("Görüntü dosyası yolu: ")
            if not os.path.isfile(image_path):
                handle_error("Dosya bulunamadı.")
                return
        elif 1 <= image_selection <= len(image_files):
            image_path = os.path.join("images", image_files[image_selection - 1])
        else:
            handle_error("Geçersiz seçim.")
            return
        
        # Basılacak tuş
        key_to_press = input("\nGörüntü bulunduğunda basılacak tuş: ")
        if not key_to_press.strip():
            handle_error("Tuş bilgisi boş olamaz.")
            return
        
        # Bulunamadığında basılacak tuş (opsiyonel)
        key_when_not_found = input("Görüntü bulunamadığında basılacak tuş (boş bırakılabilir): ")
        
        # Kontrol aralığı
        try:
            check_interval = float(input("\nKontrol aralığı (saniye): "))
            if check_interval <= 0:
                handle_error("Kontrol aralığı sıfırdan büyük olmalı.")
                return
        except ValueError:
            handle_error("Geçersiz sayı formatı.")
            return
        
        # Eşleşme eşiği
        try:
            threshold = float(input("\nEşleşme eşiği (0.1-1.0): "))
            if not 0.1 <= threshold <= 1.0:
                handle_error("Eşleşme eşiği 0.1 ile 1.0 arasında olmalı.")
                return
        except ValueError:
            handle_error("Geçersiz sayı formatı.")
            return
        
        # Görevi ekle
        task_id = add_task(
            name=name,
            image_path=image_path,
            key_to_press=key_to_press,
            key_when_not_found=key_when_not_found or None,
            check_interval=check_interval,
            threshold=threshold
        )
        
        print(f"\nGörev başarıyla eklendi! Görev ID: {task_id}")
        input("\nAna menüye dönmek için ENTER tuşuna basın...")
        
    except Exception as e:
        handle_error(f"Görev eklenirken hata oluştu: {str(e)}")

# Görev düzenleme fonksiyonu
def edit_task():
    """
    Kullanıcının kayıtlı görevlerden birini seçip
    parametrelerini düzenlemesini sağlar.
    """
    # Görevleri getir
    tasks = get_all_tasks()
    
    if not tasks:
        print("\nHenüz kayıtlı görev bulunmuyor.")
        return
    
    # Görevleri listele
    print("\n=== GÖREV DÜZENLEME ===")
    for i, task in enumerate(tasks, 1):
        print(f"{i}. {task['name']}")
    
    # Görev seçimi
    try:
        selection = int(input("\nDüzenlemek istediğiniz görevin numarasını girin (0 = İptal): "))
        
        if selection == 0:
            return
        
        if 1 <= selection <= len(tasks):
            task = tasks[selection - 1]
            task_id = task['id']
            
            print(f"\n'{task['name']}' görevi düzenleniyor:")
            print_task_info(task)
            
            # Yeni değerleri iste
            print("\nYeni değerleri girin (değiştirmek istemediğiniz alanları boş bırakın):")
            
            # Görev adı
            name = input(f"Görev adı [{task['name']}]: ")
            name = name.strip() or task['name']
            
            # Görüntü dosyası
            image_path = input(f"Görüntü dosyası yolu [{task['image_path']}]: ")
            image_path = image_path.strip() or task['image_path']
            
            # Basılacak tuş
            key_to_press = input(f"Görüntü bulunduğunda basılacak tuş [{task['key_to_press']}]: ")
            key_to_press = key_to_press.strip() or task['key_to_press']
            
            # Bulunamadığında basılacak tuş
            key_when_not_found = input(f"Görüntü bulunamadığında basılacak tuş [{task.get('key_when_not_found', '')}]: ")
            if key_when_not_found.strip():
                key_when_not_found = key_when_not_found.strip()
            else:
                key_when_not_found = task.get('key_when_not_found')
            
            # Kontrol aralığı
            check_interval_str = input(f"Kontrol aralığı (saniye) [{task['check_interval']}]: ")
            try:
                check_interval = float(check_interval_str) if check_interval_str.strip() else task['check_interval']
                if check_interval <= 0:
                    handle_error("Kontrol aralığı sıfırdan büyük olmalı.")
                    return
            except ValueError:
                handle_error("Geçersiz sayı formatı.")
                return
            
            # Eşleşme eşiği
            threshold_str = input(f"Eşleşme eşiği (0.1-1.0) [{task['threshold']}]: ")
            try:
                threshold = float(threshold_str) if threshold_str.strip() else task['threshold']
                if not 0.1 <= threshold <= 1.0:
                    handle_error("Eşleşme eşiği 0.1 ile 1.0 arasında olmalı.")
                    return
            except ValueError:
                handle_error("Geçersiz sayı formatı.")
                return
            
            # Görevi güncelle
            update_task(
                task_id=task_id,
                name=name,
                image_path=image_path,
                key_to_press=key_to_press,
                key_when_not_found=key_when_not_found,
                check_interval=check_interval,
                threshold=threshold
            )
            
            print("\nGörev başarıyla güncellendi!")
            input("\nAna menüye dönmek için ENTER tuşuna basın...")
        else:
            handle_error("Geçersiz görev numarası.")
    except ValueError:
        handle_error("Lütfen bir sayı girin.")
    except Exception as e:
        handle_error(f"Görev düzenlenirken hata oluştu: {str(e)}")

# Görev silme fonksiyonu
def delete_task_menu():
    """
    Kullanıcının kayıtlı görevlerden birini seçip
    silmesini (pasif olarak işaretlemesini) sağlar.
    """
    # Görevleri getir
    tasks = get_all_tasks()
    
    if not tasks:
        print("\nHenüz kayıtlı görev bulunmuyor.")
        return
    
    # Görevleri listele
    print("\n=== GÖREV SİLME ===")
    for i, task in enumerate(tasks, 1):
        print(f"{i}. {task['name']}")
    
    # Görev seçimi
    try:
        selection = int(input("\nSilmek istediğiniz görevin numarasını girin (0 = İptal): "))
        
        if selection == 0:
            return
        
        if 1 <= selection <= len(tasks):
            task = tasks[selection - 1]
            task_id = task['id']
            
            # Onay iste
            confirm = input(f"\n'{task['name']}' görevini silmek istediğinize emin misiniz? (e/h): ")
            if confirm.lower() != 'e':
                print("İşlem iptal edildi.")
                return
            
            # Görevi sil
            delete_task(task_id)
            
            print("\nGörev başarıyla silindi!")
            input("\nAna menüye dönmek için ENTER tuşuna basın...")
        else:
            handle_error("Geçersiz görev numarası.")
    except ValueError:
        handle_error("Lütfen bir sayı girin.")
    except Exception as e:
        handle_error(f"Görev silinirken hata oluştu: {str(e)}")

# Ana program fonksiyonu
def main():
    """
    Programın ana giriş noktası ve ana menü döngüsü.
    Kullanıcının menü seçenekleri arasında gezinmesini ve
    ilgili işlevleri çağırmasını sağlar.
    """
    # Uygulamayı başlat
    if not initialize_app():
        handle_error("Uygulama başlatılamadı.", exit_program=True)
    
    # Karşılama mesajı
    display_header()
    
    # Ana menü döngüsü
    while True:
        choice = display_menu()
        
        if choice == "1":
            # Yeni tarama başlat
            start_new_scan()
        elif choice == "2":
            # İşlem listesini göster
            list_all_tasks()
        elif choice == "3":
            # Yeni işlem ekle
            add_new_task()
        elif choice == "4":
            # İşlem düzenle
            edit_task()
        elif choice == "5":
            # İşlem sil
            delete_task_menu()
        elif choice == "0":
            # Programı sonlandır
            print("\nProgram sonlandırılıyor...")
            break
        else:
            print("\nGeçersiz seçim. Lütfen tekrar deneyin.")

# Programın doğrudan çalıştırılması durumunda ana fonksiyonu çağır
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProgram kullanıcı tarafından sonlandırıldı.")
    except Exception as e:
        handle_error(f"Beklenmeyen bir hata oluştu: {str(e)}", exit_program=True) 