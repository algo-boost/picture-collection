import pandas as pd
import pymysql
import os
import time
from datetime import datetime
import shutil  



class MySQLClient:
    def __init__(self, name, host, user, password, database):
        self.host = host
        self.name = name
        self.user = user
        self.password = password
        self.database = database
        self.connection = None
        self.connect()

    def connect(self):
        try:
            self.connection = pymysql.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database
            )
            print(f"✅ 成功连接到{self.name}MySQL数据库: vision_backend")
        except Exception as e:
            print(f"❌ 连接数据库失败: {e}")
            self.connection = None

    def query(self, sql):
        if self.connection is None:
            print("⚠️ 数据库未连接，正在尝试重新连接...")
            self.connect()
            if self.connection is None:
                print("❌ 重新连接数据库失败")
                return None
        try:
            df = pd.read_sql(sql, self.connection)
            return df
        except Exception as e:
            print(f"❌ 查询失败: {e}")
            return None

    def close(self):
        if self.connection:
            self.connection.close()
            self.connection = None
            print("🔌 数据库连接已关闭")

if '__main__' in __name__:
    name = 'changanlier'
    host = 'localhost'
    password = "12345678"
    user = 'root'
    database = 'vision_backend'
    client = MySQLClient(name=name, host=host, user=user, password=password, database=database)
    sql = """
    SELECT * FROM `product_detection_detail_result`
    where ext like '%脏污%' and c_time BETWEEN "2025-10-22 00:00:00" and "2025-10-22 23:59:59"
    """
    df = client.query(sql)
    print(df.head())
    print(df.keys())
    # df = df[['c_time', 'origin_object_key', 'check_status', 'detection_result_status', 'manual_check_status']]
    df['img_path'] = "E:/magic_fox_ai_20250826/resources/backend/local_file/" + df['origin_object_key']
    save_dir = "changanlier_2025-10-22-脏污"
    os.makedirs(save_dir, exist_ok=True)
    for i, path in enumerate(df['img_path'].values):
        img_name = os.path.basename(path)
        save_path = os.path.join(save_dir, img_name)
        if os.path.exists(save_path):
            print(f'{img_name} 已存在, 同名覆盖')
        if not os.path.exists(path):
            print(f"{i}: {path} not find")
            continue
        shutil.copy2(path, save_path)
    csv_path = os.path.join(save_dir, 'result.csv')
    df.to_csv(csv_path)

    from csv2coco import csv2coco

    csv2coco(csv_path, os.path.join(save_dir, "_annotations.coco.json"))
