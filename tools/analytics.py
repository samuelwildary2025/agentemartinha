
import json
import logging
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
from config.settings import settings

logger = logging.getLogger(__name__)

def get_db_connection():
    try:
        conn = psycopg2.connect(settings.postgres_connection_string)
        return conn
    except Exception as e:
        logger.error(f"Erro ao conectar ao DB Analytics: {e}")
        return None

def log_event(session_id: str, event_type: str, metadata: dict = None):
    """
    Registra um evento analítico.
    Tipos comuns: conversation_start, message_user, human_handoff, product_search, order_finalized
    """
    try:
        conn = get_db_connection()
        if not conn: return
        
        cur = conn.cursor()
        sql = """
            INSERT INTO analytics_events (session_id, event_type, metadata)
            VALUES (%s, %s, %s)
        """
        cur.execute(sql, (session_id, event_type, json.dumps(metadata or {})))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Erro ao logar evento {event_type}: {e}")

def get_daily_stats():
    """Retorna estatísticas do dia atual para o dashboard."""
    stats = {
        "total_conversations": 0,
        "total_orders": 0,
        "top_products": [],
        "hourly_activity": []
    }
    
    try:
        conn = get_db_connection()
        if not conn: return stats
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Total Conversas (Sessões únicas hoje)
        cur.execute("""
            SELECT COUNT(DISTINCT session_id) as total
            FROM analytics_events
            WHERE created_at >= CURRENT_DATE
        """)
        stats["total_conversations"] = cur.fetchone()['total']
        
        # 2. Total Pedidos (Eventos 'human_handoff' hoje)
        cur.execute("""
            SELECT COUNT(*) as total
            FROM analytics_events
            WHERE event_type = 'human_handoff' AND created_at >= CURRENT_DATE
        """)
        stats["total_orders"] = cur.fetchone()['total']
        
        # 3. Top Produtos (Baseado em 'product_search' metadata)
        # Assumindo que metadata tem { "query": "..." } ou { "product": "..." }
        # Vamos contar as queries de busca hoje
        cur.execute("""
            SELECT metadata->>'query' as product, COUNT(*) as count
            FROM analytics_events
            WHERE event_type = 'product_search' AND created_at >= CURRENT_DATE
            GROUP BY product
            ORDER BY count DESC
            LIMIT 5
        """)
        stats["top_products"] = cur.fetchall()
        
        # 4. Atividade por Hora
        cur.execute("""
            SELECT EXTRACT(HOUR FROM created_at) as hour, COUNT(*) as count
            FROM analytics_events
            WHERE created_at >= CURRENT_DATE
            GROUP BY hour
            ORDER BY hour ASC
        """)
        stats["hourly_activity"] = cur.fetchall()
        
        cur.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {e}")
        
    return stats

def get_recent_events(limit=20):
    """Retorna lista de últimos eventos."""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT id, session_id, event_type, metadata, created_at
            FROM analytics_events
            ORDER BY created_at DESC
            LIMIT %s
        """, (limit,))
        
        events = cur.fetchall()
        
        # Formatar data
        for e in events:
            e['created_at'] = e['created_at'].strftime("%Y-%m-%d %H:%M:%S")
            
        cur.close()
        conn.close()
        return events
    except Exception as e:
        logger.error(f"Erro ao listar eventos: {e}")
        return []
