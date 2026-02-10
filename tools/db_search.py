import psycopg2
from psycopg2.extras import RealDictCursor
from config.settings import settings
from config.logger import setup_logger

logger = setup_logger(__name__)

def _strip_accents(s: str) -> str:
    """Remove acentos de uma string de forma simples, sem dependências externas."""
    import unicodedata
    if not s:
        return s
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))

def conhecimento(query: str) -> str:
    """
    Busca produtos no banco de dados da loja (PostgreSQL) usando busca por similaridade.
    Encontra produtos mesmo com erros de digitação ou sem acentos.
    Use esta ferramenta sempre que o cliente perguntar se tem algum produto.
    
    Args:
        query: O nome ou termo do produto a ser buscado (ex: "papel crepom", "fantasia homem aranha").
    """
    conn_str = settings.products_db_connection_string
    if not conn_str:
        return "Erro: String de conexão do banco de produtos não configurada."

    query = query.strip()
    if not query:
        return "Nenhum termo de busca informado."

    # Limpar e normalizar a query
    query = query.replace("'", "").replace('"', "")
    query_normalized = _strip_accents(query).lower()
    
    table_name = settings.postgres_products_table_name

    try:
        with psycopg2.connect(conn_str) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                
                # Configurar threshold de similaridade (0.2 = 20% mínimo)
                cur.execute("SET pg_trgm.similarity_threshold = 0.2")
                
                # Busca combinada: ILIKE + Similaridade (pg_trgm)
                # Prioriza matches exatos, depois similares
                sql = f"""
                    SELECT nome, 
                           COALESCE(similarity(nome_normalizado, %s), 0) AS score
                    FROM "{table_name}"
                    WHERE 
                        nome_normalizado ILIKE %s
                        OR nome_normalizado %% %s
                    ORDER BY 
                        CASE WHEN nome_normalizado ILIKE %s THEN 1 ELSE 2 END,
                        score DESC
                    LIMIT 15
                """
                
                term_ilike = f"%{query_normalized}%"
                
                try:
                    cur.execute(sql, (query_normalized, term_ilike, query_normalized, term_ilike))
                except psycopg2.errors.UndefinedColumn:
                    # Fallback: busca simples se coluna normalizada não existir
                    conn.rollback()
                    logger.warning("Coluna nome_normalizado não encontrada, usando busca simples")
                    cur.execute(
                        f'SELECT nome FROM "{table_name}" WHERE nome ILIKE %s LIMIT 15',
                        (f"%{query}%",)
                    )
                except psycopg2.errors.UndefinedFunction:
                    # Fallback: extensão pg_trgm não instalada
                    conn.rollback()
                    logger.warning("Extensão pg_trgm não instalada, usando busca simples")
                    cur.execute(
                        f'SELECT nome FROM "{table_name}" WHERE nome ILIKE %s LIMIT 15',
                        (f"%{query}%",)
                    )
                
                results = cur.fetchall()
                
                logger.info(f"🔍 [POSTGRES] Busca por '{query}' retornou {len(results)} resultados.")
                
                if not results:
                    return "Nenhum produto encontrado com esse termo. Considere acionar o especialista humano se parecer algo que a loja venderia."
                
                return _format_results(results)

    except Exception as e:
        logger.error(f"Erro na busca Postgres: {e}")
        return f"Erro ao buscar no banco de dados: {str(e)}"

def _format_results(results: list) -> str:
    """Formata lista de dicts para o formato esperado pelo agente"""
    lines = ["PRODUTOS_ENCONTRADOS:"]
    for row in results:
        nome = row.get("nome", "").strip()
        lines.append(f"- {nome}")
    
    return "\n".join(lines)

# Alias para manter compatibilidade com http_tools.py
search_products_postgres = conhecimento

