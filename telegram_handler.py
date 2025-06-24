# telegram_handler.py
import httpx
import logging
import re
from typing import Union

logger = logging.getLogger(__name__)

class TelegramHandler:
    def __init__(self, api_token: str):
        if not api_token:
            raise ValueError("Telegram API token cannot be empty.")
        self.api_token = api_token
        self.base_url = f"https://api.telegram.org/bot{self.api_token}"

    @staticmethod
    def escape_markdownv2(text: str) -> str:
        if not isinstance(text, str):
            text = str(text)
        escape_chars = r'([_*\[\]()~`>#+\-=|{}.!])'
        return re.sub(escape_chars, r'\\\1', text)

    async def send_message(self, chat_id: str, message: str, **kwargs):
        """Sends a text-only message."""
        url = f"{self.base_url}/sendMessage"
        params = {'chat_id': chat_id, 'text': message, **kwargs}
        
        # PHIÊN BẢN DEBUG: Tạm thời bỏ qua try/except để thấy lỗi thật
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=params, timeout=20)
            response.raise_for_status() # Sẽ crash nếu có lỗi
        logger.info("Telegram text message sent successfully.")


    async def send_photo(
        self, 
        chat_id: str, 
        photo: Union[str, bytes], 
        caption: str = "", 
        **kwargs
    ):
        """Sends a photo with a caption."""
        url = f"{self.base_url}/sendPhoto"
        
        data = {'chat_id': chat_id, 'caption': caption, **kwargs}
        files = None
        
        if isinstance(photo, str):
            data['photo'] = photo
        elif isinstance(photo, bytes):
            files = {'photo': ('image.png', photo, 'image/png')}
        else:
            logger.error("Invalid photo type. Must be a URL (str) or bytes.")
            return

        # PHIÊN BẢN DEBUG: Tạm thời bỏ qua try/except để thấy lỗi thật
        async with httpx.AsyncClient() as client:
            if files:
                response = await client.post(url, data=data, files=files, timeout=30)
            else:
                response = await client.post(url, json=data, timeout=30)
            
            # Dòng này sẽ làm chương trình CRASH nếu Telegram trả về lỗi (ví dụ: 400, 403)
            # và cho chúng ta thấy traceback đầy đủ.
            response.raise_for_status() 

        logger.info("Telegram photo sent successfully.")
