
import psycopg2
from config.settings import settings

def check_schema():
    try:
        conn = psycopg2.connect(settings.postgres_connection_string)
        cur = conn.cursor()
        
        # 1. Check extensions
        print("--- EXTENSIONS ---")
        cur.execute("SELECT extname FROM pg_extension")
        rows = cur.fetchall()
        for r in rows:
            print(f"- {r[0]}")
            
        # 2. Check Table Columns
        for table_name in ['documents', 'produtos']:
            print(f"\n--- COLUMNS in '{table_name}' ---")
            cur.execute(f"""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = '{table_name}'
            """)
            rows = cur.fetchall()
            if not rows:
                print("(Table not found or no columns)")
            for r in rows:
                print(f"- {r[0]}: {r[1]}")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_schema()
