"""
Ferramenta de Busca Vetorial (Semantic Search)
Usa OpenAI Embeddings + PostgreSQL pgvector para encontrar produtos pelo significado.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from langchain_openai import OpenAIEmbeddings
from config.settings import settings
from config.logger import setup_logger

logger = setup_logger(__name__)

def get_embedding(text: str) -> list:
    """Gera embedding usando OpenAI (text-embedding-3-small)"""
    try:
        if not settings.openai_api_key or settings.openai_api_key == "sua_chave_aqui":
            logger.error("❌ OPENAI_API_KEY não configurada no .env")
            return None
            
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.openai_api_key
        )
        return embeddings.embed_query(text)
    except Exception as e:
        logger.error(f"Erro ao gerar embedding: {e}")
        return None

def search_products_vector(query: str, telefone_cliente: str = "") -> str:
    """
    Busca produtos no banco usando similaridade semântica (vetorial).
    Ideal para entender o que o cliente quer, mesmo que use termos diferentes.
    Args:
        query: Termo de busca (ex: "fita cetim azul")
        telefone_cliente: Opcional, para registro de métricas (injetado pelo agente).
    """
    query = query.strip()
    if not query:
        return "Nenhum termo de busca informado."
        
    # LOG ANALYTICS MOVED TO END

    # 1. Gerar Embedding da Query
    vector = get_embedding(query)
    if not vector:
        return "Erro: Não foi possível processar o entendimento do produto (Falha na API OpenAI)."

    conn_str = settings.products_db_connection_string
    table_name = settings.postgres_products_table_name

    try:
        with psycopg2.connect(conn_str) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                
                # Busca Híbrida (Vetorial + Keyword)
                # Combina similaridade semântica (0.7) e busca textual exata (0.3)
                
                sql = f"""
                    SELECT content, metadata,
                           (1 - (embedding <=> %s::vector)) as vector_score,
                           ts_rank(fts, websearch_to_tsquery('portuguese', %s)) as keyword_score
                    FROM "{table_name}"
                    ORDER BY 
                        ((1 - (embedding <=> %s::vector)) * 0.7) + 
                        (ts_rank(fts, websearch_to_tsquery('portuguese', %s)) * 0.3) DESC
                    LIMIT 10
                """
                
                # Converter lista para string formatada de vetor PG
                vector_str = str(vector)
                
                # Parâmetros: vector, query_text, vector, query_text
                cur.execute(sql, (vector_str, query, vector_str, query))
                results = cur.fetchall()
                
                logger.info(f"🔍 [VECTOR] Busca por '{query}' retornou {len(results)} resultados.")
                
                if not results:
                    return "Nenhum produto encontrado com características similares no catálogo."
                
                # Filtrar resultados muito distantes (opcional, threshold 0.3 por exemplo)
                # Recalcula score combinado para filtro
                filtered = []
                for r in results:
                    vec = r.get("vector_score", 0)
                    kwd = r.get("keyword_score", 0)
                    combined = (vec * 0.7) + (kwd * 0.3)
                    if combined > 0.3:
                        filtered.append(r)
                
                # LOG ANALYTICS (Deferred to capture result)
                try:
                    from tools.analytics import log_event
                    if telefone_cliente:
                        import re
                        tel = re.sub(r"\D", "", telefone_cliente)
                        
                        # Determine what to log
                        meta = {"query": query}
                        
                        # If we found something relevant
                        top_product = None
                        if filtered: top_product = filtered[0]
                        elif results: top_product = results[0] # Fallback
                        
                        if top_product:
                            # Try to get clean name from metadata, else content
                            p_meta = top_product.get("metadata") or {}
                            p_name = p_meta.get("product") or p_meta.get("nome") or top_product.get("content")
                            if p_name:
                                meta["found_product"] = str(p_name)[:100] # Limit length
                        
                        log_event(tel, "product_search", meta)
                except Exception as e:
                    logger.error(f"Erro analytics vector: {e}")

                if not filtered:
                    # Se todos forem muito ruins, retorna os top 3 mesmo assim mas com aviso
                    return _format_results(results[:3], warning=True)
                    
                return _format_results(filtered)

    except psycopg2.Error as e:
        logger.error(f"Erro no Banco Vetorial: {e}")
        return f"Erro técnico ao consultar catálogo (DB Error: {e})"
    except Exception as e:
        logger.error(f"Erro desconhecido busca vetorial: {e}")
        return "Erro ao processar busca no catálogo."

def _format_results(results: list, warning: bool = False) -> str:
    lines = ["🛒 PRODUTOS ENCONTRADOS NO CATÁLOGO:"]
    if warning:
        lines.append("(Resultados com baixa similaridade, verifique se é isso mesmo)")
        
    for row in results:
        # Tenta pegar o nome do produto no metadata se existir, senão usa o content
        metadata = row.get("metadata") or {}
        content = row.get("content", "Produto sem nome")
        
        # Se o content for muito longo, trunca
        display_name = content[:100] + "..." if len(content) > 100 else content
        
        # Calcular score final combinado para exibição
        vec = row.get("vector_score", 0)
        kwd = row.get("keyword_score", 0)
        combined = (vec * 0.7) + (kwd * 0.3)
        
        # Formatar visualmente
        lines.append(f"- {display_name} (Confiança: {combined:.2f} | V:{vec:.2f} T:{kwd:.2f})")
    
    lines.append("\n💡 DICA: Se o cliente pediu algo vago, pergunte detalhes (cor, tamanho) antes de confirmar.")
    return "\n".join(lines)

# Alias
conhecimento_vetorial = search_products_vector
