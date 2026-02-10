
import sys
import os
import psycopg2
from config.settings import settings
from config.logger import setup_logger

logger = setup_logger(__name__)

def create_table():
    try:
        conn = psycopg2.connect(settings.postgres_connection_string)
        cur = conn.cursor()
        
        # Create table if not exists
        sql = """
        CREATE TABLE IF NOT EXISTS analytics_events (
            id SERIAL PRIMARY KEY,
            session_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            metadata JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_analytics_session ON analytics_events(session_id);
        CREATE INDEX IF NOT EXISTS idx_analytics_event ON analytics_events(event_type);
        CREATE INDEX IF NOT EXISTS idx_analytics_created ON analytics_events(created_at);
        """
        
        cur.execute(sql)
        conn.commit()
        logger.info("✅ Tabela 'analytics_events' criada/verificada com sucesso!")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ Erro ao criar tabela: {e}")

if __name__ == "__main__":
    create_table()
