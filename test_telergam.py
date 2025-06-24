# test_telegram.py
import os
import asyncio
import httpx
from dotenv import load_dotenv

# ----- PHẦN KIỂM TRA CỐT LÕI -----

# 1. Tải file .env
print(">>> Bước 1: Đang tải file .env...")
load_dotenv()
print("     File .env đã được tải.")

# 2. Lấy thông tin credentials
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

print("\n>>> Bước 2: Kiểm tra các biến môi trường...")
if not TELEGRAM_BOT_TOKEN or len(TELEGRAM_BOT_TOKEN) < 20: # Basic check
    print("     LỖI: Không tìm thấy TELEGRAM_BOT_TOKEN trong file .env hoặc token không hợp lệ!")
    exit()
if not TELEGRAM_CHAT_ID:
    print("     LỖI: Không tìm thấy TELEGRAM_CHAT_ID trong file .env!")
    exit()

print("     OK! Đã tìm thấy TOKEN và CHAT_ID.")
print(f"     CHAT_ID của bạn là: {TELEGRAM_CHAT_ID}")


# 3. Hàm gửi tin nhắn kiểm tra
async def send_test_message():
    """Hàm này chỉ dùng để kiểm tra việc gửi tin nhắn."""
    print("\n>>> Bước 3: Đang chuẩn bị gửi tin nhắn kiểm tra tới Telegram...")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    # Dùng tin nhắn đơn giản không format để kiểm tra
    params = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': '✅ Hello from the test script! If you see this, your .env config is correct.',
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=params, timeout=20)
            
            print(f"     Telegram API trả về mã trạng thái: {response.status_code}")
            
            if response.status_code == 200:
                print("\n🎉 THÀNH CÔNG! Tin nhắn đã được gửi đi. Vui lòng kiểm tra Telegram của bạn.")
            else:
                print("\n❌ THẤT BẠI! Telegram đã từ chối yêu cầu. Phản hồi từ server:")
                print(f"     {response.text}")
                print("\n     GỢI Ý: Lỗi này thường do CHAT_ID sai hoặc bot chưa được thêm vào nhóm.")

    except Exception as e:
        print(f"\n❌ LỖI NGHIÊM TRỌNG: Đã có lỗi xảy ra khi cố gắng kết nối tới Telegram. Lỗi: {e}")
        print("     GỢI Ý: Kiểm tra lại BOT_TOKEN có bị sai không, hoặc kiểm tra kết nối mạng của server.")

# 4. Chạy hàm kiểm tra
if __name__ == "__main__":
    asyncio.run(send_test_message())

