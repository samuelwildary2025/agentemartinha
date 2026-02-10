
import sys
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from langchain_openai import OpenAIEmbeddings
from config.settings import settings
from config.logger import setup_logger
import time

# Config logger
logger = setup_logger("fix_embeddings")

def fix_embeddings():
    try:
        logger.info("🔌 Conectando ao banco de dados...")
        conn = psycopg2.connect(settings.postgres_connection_string)
        conn.autocommit = True
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Garantir Extensão e Tabela
        logger.info("🛠️ Verificando schema...")
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        
        table_name = settings.postgres_products_table_name
        logger.info(f"📋 Tabela Alvo: {table_name}")
        
        # Verifica se a tabela existe
        cur.execute(f"SELECT to_regclass('public.{table_name}');")
        if not cur.fetchone()['to_regclass']:
            logger.error(f"❌ Tabela '{table_name}' não encontrada! Importe os produtos primeiro.")
            return

        # 2. Adicionar Coluna se não existir
        try:
            cur.execute(f"ALTER TABLE {table_name} ADD COLUMN embedding vector(1536);")
            logger.info("✅ Coluna 'embedding' adicionada.")
        except psycopg2.errors.DuplicateColumn:
            logger.info("ℹ️ Coluna 'embedding' já existe.")
            
        # 3. Criar Índice
        try:
            cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_embedding ON {table_name} USING hnsw (embedding vector_cosine_ops);")
            logger.info("✅ Índice HNSW criado/verificado.")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao criar índice (pode ser ignorado se já existir): {e}")

        # ... (rest of the script) ...

        # 5. Buscar produtos sem embedding
        logger.info("🔍 Buscando produtos sem embedding...")
        # Verificar colunas
        cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}'")
        cols = [row['column_name'] for row in cur.fetchall()]
        
        target_cols = []
        if 'page_content' in cols: target_cols.append('page_content') # LlamaIndex/LangChain default
        elif 'content' in cols: target_cols.append('content')
        else:
            if 'nome' in cols: target_cols.append('nome')
            if 'descricao' in cols: target_cols.append('descricao')
            if 'categoria' in cols: target_cols.append('categoria')
        
        if not target_cols:
            logger.error(f"❌ Não encontrei colunas de texto em '{table_name}'. Colunas disponíveis: {cols}")
            return
            
        logger.info(f"📝 Usando colunas {target_cols} para vetorização.")
        
        # Selecionar IDs que precisam de update
        pk = 'id' if 'id' in cols else 'uuid'
        if pk not in cols:
             # Tenta achar PK
             cur.execute(f"SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) WHERE i.indrelid = '{table_name}'::regclass AND i.indisprimary;")
             res = cur.fetchone()
             if res: pk = res['attname']
             else: pk = cols[0] # Fallback
        
        cur.execute(f"SELECT {pk}, {', '.join(target_cols)} FROM {table_name} WHERE embedding IS NULL")
        rows = cur.fetchall()
        
        total = len(rows)
        logger.info(f"📊 Total de produtos para processar: {total}")
        
        if total == 0:
            logger.info("✨ Todos os produtos já possuem embedding!")
            return

        # 6. Processar em lotes
        batch_size = 50
        for i in range(0, total, batch_size):
            batch = rows[i:i+batch_size]
            texts = []
            ids = []
            
            for row in batch:
                # Concatenar texto
                text_parts = [str(row[c]) for c in target_cols if row[c]]
                text = " ".join(text_parts)
                texts.append(text)
                ids.append(row[pk])
            
            try:
                # Gerar embeddings
                vectors = embeddings_model.embed_documents(texts)
                
                # Atualizar no banco
                for pid, vec in zip(ids, vectors):
                    cur.execute(f"UPDATE {table_name} SET embedding = %s WHERE {pk} = %s", (vec, pid))
                
                logger.info(f"✅ Processado {i + len(batch)}/{total}")
                time.sleep(0.5) 
                
            except Exception as e:
                logger.error(f"❌ Erro no lote {i}: {e}")
                time.sleep(5)

        logger.info("🎉 Processamento concluído com sucesso!")
        conn.close()

    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}")

if __name__ == "__main__":
    fix_embeddings()
