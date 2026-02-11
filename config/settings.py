"""
Configurações do Agente de Supermercado
Carrega variáveis de ambiente usando Pydantic Settings
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Configurações da aplicação carregadas do .env"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # LLM Provider (openai ou google)
    openai_api_key: Optional[str] = None
    openai_api_base: Optional[str] = None  # Para xAI Grok ou outros provedores OpenAI-compatíveis
    xai_api_key: Optional[str] = None      # Chave específica da xAI
    google_api_key: Optional[str] = None
    llm_model: str = "gemini-2.0-flash-lite"
    llm_temperature: float = 0.3
    llm_provider: str = "google"
    moonshot_api_key: Optional[str] = None
    moonshot_api_url: str = "https://api.moonshot.ai/anthropic"
    
    # Postgres (Memória + Produtos - Mesmo banco)
    postgres_connection_string: str = "postgres://postgres:85885885@31.97.252.6:6087/festinfan-bd-produtos?sslmode=disable"
    postgres_table_name: str = "memoria"
    postgres_products_table_name: str = "documents"
    postgres_message_limit: int = 20
    
    # Banco de Produtos (Postgres)
    # Se for o mesmo banco, pode usar a mesma connection string
    products_db_connection_string: Optional[str] = "postgres://postgres:85885885@31.97.252.6:6087/festinfan-bd-produtos?sslmode=disable"
    
    # Redis (Buffer de mensagens + Cooldown)
    redis_host: str = "31.97.252.6"
    redis_port: int = 9886
    redis_password: Optional[str] = "85885885"
    redis_db: int = 0
    
    # API do Supermercado
    supermercado_base_url: str = ""
    supermercado_auth_token: str = ""

    # Consulta de EAN (estoque/preço)
    estoque_ean_base_url: str = ""

    # EAN Smart Responder (Supabase Functions)
    smart_responder_url: Optional[str] = None
    smart_responder_token: Optional[str] = None
    smart_responder_auth: str = ""
    smart_responder_apikey: str = ""
    pre_resolver_enabled: bool = False
    
    # WhatsApp API (Nova Integração)
    whatsapp_api_base_url: Optional[str] = None
    whatsapp_instance_token: Optional[str] = None  # Header: X-Instance-Token
    
    # WhatsApp / UAZ API (Legado/Compatibilidade)
    whatsapp_api_url: Optional[str] = None 
    uaz_api_url: Optional[str] = None
    whatsapp_token: Optional[str] = None
    whatsapp_method: str = "POST"
    whatsapp_agent_number: Optional[str] = None
    
    # Human Takeover - Tempo de pausa quando atendente humano assume (em segundos)
    # 8 horas = 28800 segundos
    human_takeover_ttl: int = 28800 
    
    # ID da etiqueta "Novo Pedido" no WhatsApp (usar GET /labels para descobrir)
    # Esta etiqueta é adicionada ao chat quando o agente transfere para o atendente
    novo_pedido_label_id: Optional[str] = "558591836205:2" 
    
    # Lista Negra de Telefones (Ignorar)
    # Formato: "558599999999,558588888888" (separado por vírgula)
    blocked_numbers: str = "558594147403,558587781140,558596535100,558596535300,558597054444,558597621595,558588664068,5585985296922,5585996275067,558589823370"

    # Servidor
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    debug_mode: bool = False

    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/agente.log"
    
    agent_prompt_path: Optional[str] = "prompts/agent_system_optimized.md"

    # Dashboard Auth
    dashboard_user: str = "admin"
    dashboard_password: str = "123456"


# Instância global de configurações
settings = Settings()
