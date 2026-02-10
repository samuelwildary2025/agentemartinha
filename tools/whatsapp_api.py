import requests
import json
import re
from typing import Optional, Dict, Any
from config.settings import settings
from config.logger import setup_logger

logger = setup_logger(__name__)

class WhatsAppAPI:
    def __init__(self):
        self.base_url = (settings.whatsapp_api_base_url or "").rstrip("/")
        self.token = settings.whatsapp_instance_token
        
        if not self.base_url:
            logger.warning("WHATSAPP_API_BASE_URL não configurado!")
            
    def _get_headers(self):
        # Tenta cobrir vários padrões de auth de APIs de WhatsApp
        return {
            "Content-Type": "application/json",
            "apikey": self.token,
            "token": self.token,
            "Authorization": f"Bearer {self.token}",
            "X-Instance-Token": self.token # Header específico confirmado no teste
        }

    def _clean_number(self, phone: str) -> str:
        """Remove caracteres não numéricos"""
        return re.sub(r"\D", "", str(phone))

    def send_text(self, to: str, text: str) -> bool:
        """
        Envia mensagem de texto simples
        POST /send/text
        """
        if not self.base_url: return False
        
        url = f"{self.base_url}/send/text"
        payload = {
            "number": self._clean_number(to),
            "text": text
        }
        
        try:
            resp = requests.post(url, headers=self._get_headers(), json=payload, timeout=10)
            resp.raise_for_status()
            # UAZAPI v2 usually returns { "id": "...", "status": "PENDING" }
            return True
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem WhatsApp para {to}: {e}")
            return False

    def send_presence(self, to: str, presence: str = "composing") -> bool:
        """
        Envia status de presença (digitando...)
        POST /message/presence
        Valores: composing, recording, available, unavailable
        """
        if not self.base_url: return False
        
        url = f"{self.base_url}/message/presence"
        payload = {
            "number": self._clean_number(to),
            "presence": presence,
            "delay": 0
        }
        
        try:
            requests.post(url, headers=self._get_headers(), json=payload, timeout=5)
            return True
        except Exception:
            return False

    def mark_as_read(self, chat_id: str) -> bool:
        """
        Marca a conversa como lida (Tick Azul)
        POST /chat/read
        Body: { "number": "55...@s.whatsapp.net", "read": true }
        """
        if not self.base_url or not chat_id: return False
        
        # Garante formatação JID
        jid = chat_id if "@" in chat_id else f"{self._clean_number(chat_id)}@s.whatsapp.net"
        
        url = f"{self.base_url}/chat/read"
        payload = {"number": jid, "read": True}
        
        try:
            resp = requests.post(url, headers=self._get_headers(), json=payload, timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def get_media_base64(self, message_id: str) -> Optional[Dict[str, str]]:
        """
        Obtém mídia em Base64
        POST /message/download
        Retorna dict com 'base64' e 'mimetype'
        """
        if not self.base_url: return None
        
        url = f"{self.base_url}/message/download"
        payload = {
            "id": message_id,
            "return_link": False,
            "return_base64": True
        }
        
        logger.info(f"🌐 DEBUG API CALL: {url} | ID: {message_id}")
        
        try:
            resp = requests.post(url, headers=self._get_headers(), json=payload, timeout=30)
            logger.info(f"🌐 DEBUG API RESPONSE: Status={resp.status_code}") 
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success") and "data" in data:
                    return data["data"]
                if "base64" in data:
                    return data
            else:
                logger.warning(f"⚠️ Erro API Mídia ({resp.status_code}): {resp.text[:200]}")
        except Exception as e:
            logger.error(f"Erro ao obter mídia WhatsApp ({message_id}): {e}")
            
        return None

    def get_labels(self) -> list:
        """
        Lista todas as etiquetas disponíveis
        GET /labels
        """
        if not self.base_url: return []
        
        url = f"{self.base_url}/labels"
        
        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                # Pode retornar como { data: [...] } ou direto [...]
                if isinstance(data, list):
                    return data
                return data.get("data", data.get("labels", []))
        except Exception as e:
            logger.error(f"Erro ao listar etiquetas: {e}")
        return []

    def add_label_to_chat(self, chat_id: str, label_id: str) -> bool:
        """
        Adiciona uma etiqueta a um chat
        POST /chat/labels
        Body: { "number": "55...@s.whatsapp.net", "add_labelid": "72" }
        """
        if not self.base_url or not chat_id or not label_id: return False
        
        # Garante formatação JID (s.whatsapp.net para users)
        jid = chat_id if "@" in chat_id else f"{self._clean_number(chat_id)}@s.whatsapp.net"
        
        url = f"{self.base_url}/chat/labels"
        payload = {
            "number": jid,
            "add_labelid": str(label_id)
        }
        
        try:
            resp = requests.post(url, headers=self._get_headers(), json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info(f"🏷️ Etiqueta {label_id} adicionada ao chat {chat_id}")
                return True
            else:
                logger.warning(f"⚠️ Erro ao adicionar etiqueta ({resp.status_code}): {resp.text[:200]}")
        except Exception as e:
            logger.error(f"Erro ao adicionar etiqueta ao chat: {e}")
        return False

    def remove_label_from_chat(self, chat_id: str, label_id: str) -> bool:
        """
        Remove uma etiqueta de um chat
        POST /chat/labels
        Body: { "number": "55...@s.whatsapp.net", "remove_labelid": "72" }
        """
        if not self.base_url or not chat_id or not label_id: return False
        
        jid = chat_id if "@" in chat_id else f"{self._clean_number(chat_id)}@s.whatsapp.net"
        
        url = f"{self.base_url}/chat/labels"
        payload = {
            "number": jid,
            "remove_labelid": str(label_id)
        }
        
        try:
            resp = requests.post(url, headers=self._get_headers(), json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info(f"🏷️ Etiqueta {label_id} removida do chat {chat_id}")
                return True
        except Exception as e:
            logger.error(f"Erro ao remover etiqueta: {e}")
        return False

# Instância global
whatsapp = WhatsAppAPI()
