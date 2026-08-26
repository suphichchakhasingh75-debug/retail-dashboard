import os
import duckdb
import pandas as pd

# กำหนดการตั้งค่าแสดงผล Pandas ให้เห็นทุกคอลัมน์ชัดเจน
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

def find_duckdb_path():
    """ค้นหาตำแหน่งไฟล์ dev.duckdb อัตโนมัติ"""
    possible_paths = [
        "retail_data/dev.duckdb",
        "dev.duckdb",
        "../retail_data/dev.duckdb"
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None

def main():
    db_path = find_duckdb_path()
    
    if not db_path:
        print("❌ ไม่พบไฟล์ dev.duckdb ในโปรเจกต์ กรุณาตรวจสอบว่าสั่ง `dbt run` เรียบร้อยแล้วหรือยัง")
        return

    print(f"✅ เชื่อมต่อฐานข้อมูล DuckDB สำเร็จ: {db_path}\n")

    try:
        # เชื่อมต่อแบบ read_only เพื่อป้องกันไฟล์ล็อก
        conn = duckdb.connect(db_path, read_only=True)

        # 1. แสดงรายชื่อ Tables และ Views ทั้งหมด
        print("======== 1. รายชื่อ TABLES & VIEWS ทั้งหมด ========")
        tables_df = conn.execute("SHOW TABLES;").df()
        
        if tables_df.empty:
            print("ไม่พบตารางในฐานข้อมูล")
            return

        print(tables_df.to_string(index=False))
        print("\n" + "="*50 + "\n")

        # 2. แสดงจำนวนข้อมูล (Row Count) แต่ละตาราง
        print("======== 2. จำนวนแถวข้อมูล (ROW COUNTS) ========")
        tables_list = tables_df['name'].tolist()
        for table in tables_list:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {table};").fetchone()[0]
                print(f"  • {table:<25} : {count:>7,} แถว")
            except Exception as e:
                print(f"  • {table:<25} : Error ({e})")
        
        print("\n" + "="*50 + "\n")

        # 3. ดูตัวอย่างข้อมูล Top 5 แถวของตาราง Staging ตัวอย่าง
        sample_table = "stg_orders" if "stg_orders" in tables_list else tables_list[0]
        print(f"======== 3. ตัวอย่างข้อมูล Top 5 แถวจาก '{sample_table}' ========")
        sample_df = conn.execute(f"SELECT * FROM {sample_table} LIMIT 5;").df()
        print(sample_df)

        conn.close()

    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการรัน Query: {e}")

if __name__ == "__main__":
    main()