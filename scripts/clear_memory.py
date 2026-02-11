
import psycopg2
import redis
import os
from dotenv import load_dotenv

load_dotenv()

# --- LIMPAR POSTGRES (MEMÓRIA) ---
print("🧹 Limpando Memória Postgres...")
try:
    conn_str = os.getenv("POSTGRES_CONNECTION_STRING")
    table_name = os.getenv("POSTGRES_TABLE_NAME", "memoria")
    
    conn = psycopg2.connect(conn_str)
    cur = conn.cursor()
    
    cur.execute(f"DELETE FROM {table_name}")
    deleted = cur.rowcount
    conn.commit()
    
    cur.close()
    conn.close()
    print(f"✅ Postgres: {deleted} mensagens apagadas.")
except Exception as e:
    print(f"❌ Erro Postgres: {e}")


# --- LIMPAR REDIS (BUFFER/COOLDOWN) ---
print("\n🧹 Limpando Redis...")
try:
    client = redis.Redis(
        host=os.getenv("REDIS_HOST", "31.97.252.6"),
        port=int(os.getenv("REDIS_PORT", 9886)),
        db=0,
        password=os.getenv("REDIS_PASSWORD", "85885885"),  # Fallback para senha do settings.py
        decode_responses=True
    )
    
    # Apagar chaves específicas do telefone de teste
    tel = "558587520060"
    keys = [f"msgbuf:{tel}", f"cooldown:{tel}"]
    
    count = 0
    for k in keys:
        if client.delete(k):
            count += 1
            print(f"   - Chave apagada: {k}")
            
    print(f"✅ Redis: {count} chaves apagadas.")
    
except Exception as e:
    print(f"❌ Erro Redis: {e}")

print("\n✨ Limpeza concluída!")
