
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
        "avg_response_time": None,
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
        
        # 3. Tempo Médio de Resposta (segundos)
        cur.execute("""
            SELECT AVG((metadata->>'seconds')::float) as avg_time
            FROM analytics_events
            WHERE event_type = 'response_time' AND created_at >= CURRENT_DATE
        """)
        row = cur.fetchone()
        if row and row['avg_time']:
            stats["avg_response_time"] = round(row['avg_time'], 1)
        
        # 4. Top Produtos (Baseado em 'product_search' metadata)
        cur.execute("""
            SELECT COALESCE(metadata->>'found_product', metadata->>'query') as product, COUNT(*) as count
            FROM analytics_events
            WHERE event_type = 'product_search' AND created_at >= CURRENT_DATE
            GROUP BY product
            ORDER BY count DESC
            LIMIT 5
        """)
        stats["top_products"] = cur.fetchall()
        
        # 5. Atividade por Hora
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

def get_all_contacts():
    """Retorna lista de contatos (sessões) com data da última mensagem."""
    try:
        conn = get_db_connection()
        if not conn: return []
        
        # O nome da tabela de mensagens é definido no settings.py (postgres_table_name)
        table_name = settings.postgres_table_name
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Pega sessões distintas. 
        # ATENÇÃO: A tabela message_store do LangChain não tem 'updated_at' fácil, 
        # mas podemos assumir que session_id é o telefone.
        # Se a tabela tiver estrutura padrão do PostgresChatMessageHistory: (id, session_id, message, created_at)
        # Vamos tentar pegar a última mensagem de cada sessão.
        
        # Verifica colunas da tabela primeiro para evitar erro
        cur.execute(f"SELECT * FROM {table_name} LIMIT 0")
        colnames = [desc[0] for desc in cur.description]
        
        if 'created_at' in colnames:
            sql = f"""
                SELECT session_id as phone, MAX(created_at) as last_interaction
                FROM {table_name}
                GROUP BY session_id
                ORDER BY last_interaction DESC
            """
        else:
            # Fallback se não tiver timestamp (improvável se for schema padrão)
            sql = f"""
                SELECT DISTINCT session_id as phone, NULL as last_interaction
                FROM {table_name}
            """
            
        cur.execute(sql)
        contacts = cur.fetchall()
        
        # Formatar data
        for c in contacts:
            if c.get('last_interaction'):
                c['last_interaction'] = c['last_interaction'].strftime("%Y-%m-%d %H:%M:%S")
            else:
                c['last_interaction'] = "N/A"
                
        cur.close()
        conn.close()
        return contacts
    except Exception as e:
        logger.error(f"Erro ao listar contatos: {e}")
        return []

def get_chat_history(phone: str):
    """Retorna histórico de mensagens de um telefone específico."""
    try:
        conn = get_db_connection()
        if not conn: return []
        
        table_name = settings.postgres_table_name
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Schema padrão LangChain: id, session_id, message (jsonb), created_at (opcional)
        # message field is JSONB: {"type": "human/ai", "data": {"content": "..."}}
        
        sql = f"""
            SELECT message, id
            FROM {table_name}
            WHERE session_id = %s
            ORDER BY id ASC
        """
        
        cur.execute(sql, (phone,))
        rows = cur.fetchall()
        
        history = []
        for r in rows:
            msg_data = r['message']
            # Tenta decodificar se for string
            if isinstance(msg_data, str):
                msg_data = json.loads(msg_data)
                
            # Extrair conteúdo útil
            msg_type = msg_data.get("type", "unknown")
            content = msg_data.get("data", {}).get("content") or msg_data.get("content", "")
            
            if content:
                history.append({
                    "role": "user" if msg_type == "human" else "assistant",
                    "content": content,
                    "type": msg_type
                })
                
        cur.close()
        conn.close()
        return history
    except Exception as e:
        logger.error(f"Erro ao obter histórico ({phone}): {e}")
        return []


def generate_daily_insight():
    """
    Gera um insight diário usando OpenAI baseado nos dados de analytics do dia.
    Chamado automaticamente às 17:00 pelo scheduler.
    """
    try:
        # 1. Coletar dados do dia
        stats = get_daily_stats()
        
        # 2. Montar contexto para a IA
        top_products_str = ""
        if stats.get("top_products"):
            top_products_str = ", ".join([f"{p['product']} ({p['count']}x)" for p in stats["top_products"]])
        else:
            top_products_str = "Nenhum produto pesquisado hoje."
        
        avg_time = stats.get("avg_response_time")
        avg_time_str = f"{avg_time}s" if avg_time else "sem dados"
        
        summary = (
            f"Resumo do dia:\n"
            f"- Total de atendimentos: {stats.get('total_conversations', 0)}\n"
            f"- Pedidos finalizados: {stats.get('total_orders', 0)}\n"
            f"- Tempo médio de resposta: {avg_time_str}\n"
            f"- Produtos mais procurados: {top_products_str}\n"
        )
        
        # 3. Chamar OpenAI para gerar insight
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Você é um analista de dados de uma loja de artigos para festa chamada Festinfan e Amelinha. "
                        "Gere um insight de negócio curto e útil (máximo 2 frases) baseado nos dados fornecidos. "
                        "Seja direto e prático. Use linguagem simples. "
                        "Se não houver dados suficientes, dê uma dica geral sobre o negócio."
                    )
                },
                {
                    "role": "user",
                    "content": summary
                }
            ],
            max_tokens=150,
            temperature=0.7
        )
        
        insight_text = response.choices[0].message.content.strip()
        
        # 4. Salvar no banco como evento analytics
        log_event("system", "daily_insight", {
            "text": insight_text,
            "stats_summary": summary
        })
        
        logger.info(f"✨ Insight diário gerado: {insight_text[:100]}...")
        return insight_text
        
    except Exception as e:
        logger.error(f"Erro ao gerar insight diário: {e}")
        return None


def get_latest_insight():
    """Retorna o insight mais recente."""
    try:
        conn = get_db_connection()
        if not conn: return None
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT metadata->>'text' as text, created_at
            FROM analytics_events
            WHERE event_type = 'daily_insight'
            ORDER BY created_at DESC
            LIMIT 1
        """)
        
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if row:
            return {
                "text": row["text"],
                "date": row["created_at"].strftime("%d/%m/%Y %H:%M")
            }
        return None
        
    except Exception as e:
        logger.error(f"Erro ao obter insight: {e}")
        return None
