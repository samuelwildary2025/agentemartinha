
import psycopg2
import os
import json
from dotenv import load_dotenv

load_dotenv()

# Conectar ao banco
try:
    conn_str = os.getenv("POSTGRES_CONNECTION_STRING")
    print(f"🔌 Conectando ao banco: {conn_str}")
    
    conn = psycopg2.connect(conn_str)
    cur = conn.cursor()
    
    # Listar as tabelas
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
    tables = cur.fetchall()
    print(f"\n📁 Tabelas encontradas no banco: {[t[0] for t in tables]}")
    
    # Verificar conteúdo da tabela 'memoria'
    table_name = os.getenv("POSTGRES_TABLE_NAME", "memoria")
    
    print(f"\n🔍 Verificando tabela '{table_name}':")
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cur.fetchone()[0]
    print(f"   Total de mensagens: {count}")
    
    if count > 0:
        cur.execute(f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT 5")
        rows = cur.fetchall()
        print("\n   Últimas 5 mensagens:")
        for row in rows:
            print(f"   ID: {row[0]} | Sessão: {row[1]} | Msg: {str(row[2])[:50]}...")
    else:
        print("   ⚠️ Tabela vazia!")

    cur.close()
    conn.close()

except Exception as e:
    print(f"\n❌ Erro ao conectar/consultar: {e}")
