from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
import pandas as pd
import pymysql
import os
import time
from datetime import datetime
import shutil
import json
import uuid
import zipfile
from csv2coco import csv2coco

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'exports'
CONFIG_FILE = 'config.json'

# 确保导出目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/images', exist_ok=True)

# 默认配置
DEFAULT_CONFIG = {
    'db_host': 'localhost',
    'db_user': 'root',
    'db_password': '12345678',
    'db_database': 'vision_backend',
    'img_base_path': 'E:/magic_fox_ai_20250826/resources/backend/local_file/',
    'img_path_mode': 'concat',  # 'full_path' 或 'concat'
    'img_path_field': 'origin_object_key',  # 用于拼接的字段名
    'img_full_path_field': 'local_pic_url',  # 完整路径字段名
    'default_sql': "SELECT * FROM `product_detection_detail_result` WHERE ext like '%脏污%' AND c_time BETWEEN '${START_TIME}' AND '${END_TIME}'",
    'id2name': {
        '0': '其他', '1': '划伤', '2': '压痕', 
        '3': '吊紧', '4': '异物外漏', '5': '折痕', '6': '抛线',
        '7': '拼接间隙', '8': '水渍', '9': '烫伤', '10': '破损', 
        '11': '碰伤', '12': '红标签', '13': '线头', '14': '脏污', 
        '15': '褶皱(T型)', '16': '褶皱（重度）', '17': '重跳针'
    }
}

# 配置管理函数
def load_config():
    """加载配置文件"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # 合并默认配置，确保所有字段都存在
                merged_config = DEFAULT_CONFIG.copy()
                merged_config.update(config)
                # 确保 id2name 存在且是字典格式
                if 'id2name' not in merged_config or not isinstance(merged_config.get('id2name'), dict):
                    merged_config['id2name'] = DEFAULT_CONFIG['id2name']
                return merged_config
        except Exception as e:
            print(f"⚠️ 加载配置文件失败: {e}，使用默认配置")
            return DEFAULT_CONFIG
    return DEFAULT_CONFIG

def save_config(config):
    """保存配置文件"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"❌ 保存配置文件失败: {e}")
        return False

# 加载配置
APP_CONFIG = load_config()

# 数据库配置（优先使用配置文件，其次环境变量，最后默认值）
DB_CONFIG = {
    'host': os.getenv('DB_HOST', APP_CONFIG.get('db_host', DEFAULT_CONFIG['db_host'])),
    'user': os.getenv('DB_USER', APP_CONFIG.get('db_user', DEFAULT_CONFIG['db_user'])),
    'password': os.getenv('DB_PASSWORD', APP_CONFIG.get('db_password', DEFAULT_CONFIG['db_password'])),
    'database': os.getenv('DB_DATABASE', APP_CONFIG.get('db_database', DEFAULT_CONFIG['db_database']))
}

# 图片基础路径配置
IMG_BASE_PATH = os.getenv('IMG_BASE_PATH', APP_CONFIG.get('img_base_path', DEFAULT_CONFIG['img_base_path']))


class MySQLClient:
    def __init__(self, host, user, password, database):
        self.host = host
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
                database=self.database,
                charset='utf8mb4'
            )
            print(f"✅ 成功连接到MySQL数据库: {self.database}")
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


# 全局数据库客户端
db_client = None


def get_db_client():
    global db_client, DB_CONFIG, APP_CONFIG
    # 重新加载配置以确保使用最新配置
    APP_CONFIG = load_config()
    DB_CONFIG = {
        'host': APP_CONFIG.get('db_host', DEFAULT_CONFIG['db_host']),
        'user': APP_CONFIG.get('db_user', DEFAULT_CONFIG['db_user']),
        'password': APP_CONFIG.get('db_password', DEFAULT_CONFIG['db_password']),
        'database': APP_CONFIG.get('db_database', DEFAULT_CONFIG['db_database'])
    }
    
    if db_client is None:
        db_client = MySQLClient(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database']
        )
    return db_client


def update_config_and_reconnect(new_config):
    """更新配置并重新连接数据库"""
    global db_client, DB_CONFIG, IMG_BASE_PATH, APP_CONFIG
    
    # 保存配置
    if save_config(new_config):
        APP_CONFIG = new_config
        DB_CONFIG = {
            'host': new_config.get('db_host', DEFAULT_CONFIG['db_host']),
            'user': new_config.get('db_user', DEFAULT_CONFIG['db_user']),
            'password': new_config.get('db_password', DEFAULT_CONFIG['db_password']),
            'database': new_config.get('db_database', DEFAULT_CONFIG['db_database'])
        }
        IMG_BASE_PATH = new_config.get('img_base_path', DEFAULT_CONFIG['img_base_path'])
        
        # 关闭旧连接
        if db_client:
            try:
                db_client.close()
            except:
                pass
            db_client = None
        
        # 创建新连接
        get_db_client()
        return True
    return False


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/config')
def config_page():
    return render_template('config.html')


@app.route('/api/config', methods=['GET'])
def get_config():
    """获取当前配置"""
    try:
        config = load_config()
        # 不返回密码（安全考虑）
        safe_config = config.copy()
        return jsonify({'success': True, 'config': safe_config})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/config', methods=['POST'])
def save_config_api():
    """保存配置"""
    try:
        data = request.json
        config = data.get('config', {})
        
        # 验证必填字段
        required_fields = ['db_host', 'db_user', 'db_password', 'db_database']
        for field in required_fields:
            if field not in config:
                return jsonify({'success': False, 'error': f'缺少必填字段: {field}'}), 400
        
        # 如果使用拼接模式，需要 img_base_path
        if config.get('img_path_mode', 'concat') == 'concat' and 'img_base_path' not in config:
            return jsonify({'success': False, 'error': '使用拼接模式时需要提供 img_base_path'}), 400
        
        # 更新配置并重新连接
        if update_config_and_reconnect(config):
            return jsonify({'success': True, 'message': '配置保存成功'})
        else:
            return jsonify({'success': False, 'error': '保存配置失败'}), 500
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/config/test-connection', methods=['POST'])
def test_connection():
    """测试数据库连接"""
    try:
        data = request.json
        host = data.get('host', '')
        user = data.get('user', '')
        password = data.get('password', '')
        database = data.get('database', '')
        
        if not all([host, user, password, database]):
            return jsonify({'success': False, 'error': '请填写完整的数据库连接信息'}), 400
        
        # 尝试连接
        test_client = MySQLClient(host, user, password, database)
        if test_client.connection:
            test_client.close()
            return jsonify({'success': True, 'message': '数据库连接成功'})
        else:
            return jsonify({'success': False, 'error': '数据库连接失败'}), 500
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/query', methods=['POST'])
def query_database():
    """执行 SQL 查询"""
    try:
        data = request.json
        sql_template = data.get('sql', '')
        start_time = data.get('start_time', '')
        end_time = data.get('end_time', '')
        sample_size = data.get('sample_size', None)  # 随机采样数量
        
        if not sql_template:
            return jsonify({'success': False, 'error': 'SQL 查询语句不能为空'}), 400
        
        # 替换 SQL 中的时间变量
        sql = sql_template.replace('${START_TIME}', start_time).replace('${END_TIME}', end_time)
        
        # 执行查询
        client = get_db_client()
        df = client.query(sql)
        
        if df is None:
            return jsonify({'success': False, 'error': '查询失败，请检查 SQL 语句和数据库连接'}), 500
        
        if df.empty:
            return jsonify({'success': True, 'data': [], 'count': 0, 'message': '查询结果为空'})
        
        # 随机采样（如果指定了采样数量）
        if sample_size is not None and sample_size > 0:
            sample_size = int(sample_size)
            if sample_size < len(df):
                df = df.sample(n=sample_size, random_state=42).reset_index(drop=True)
        
        # 处理图片路径（使用最新配置）
        global IMG_BASE_PATH
        APP_CONFIG = load_config()
        IMG_BASE_PATH = APP_CONFIG.get('img_base_path', DEFAULT_CONFIG['img_base_path'])
        img_path_mode = APP_CONFIG.get('img_path_mode', DEFAULT_CONFIG['img_path_mode'])
        img_path_field = APP_CONFIG.get('img_path_field', DEFAULT_CONFIG['img_path_field'])
        img_full_path_field = APP_CONFIG.get('img_full_path_field', DEFAULT_CONFIG['img_full_path_field'])
        
        # 根据配置的路径处理模式来设置图片路径
        if img_path_mode == 'full_path':
            # 使用完整路径字段
            if img_full_path_field in df.columns:
                df['img_path'] = df[img_full_path_field].astype(str)
            else:
                print(f"⚠️ 警告：未找到完整路径字段 '{img_full_path_field}'，尝试使用其他方式")
                if 'local_pic_url' in df.columns:
                    df['img_path'] = df['local_pic_url'].astype(str)
                elif 'img_path' in df.columns:
                    df['img_path'] = df['img_path'].astype(str)
                else:
                    print(f"❌ 错误：无法确定图片路径，请检查配置")
        elif img_path_mode == 'concat':
            # 使用拼接方式
            if img_path_field in df.columns:
                # 确保基础路径以 / 结尾
                base_path = IMG_BASE_PATH if IMG_BASE_PATH.endswith('/') or IMG_BASE_PATH.endswith('\\') else IMG_BASE_PATH + '/'
                df['img_path'] = base_path + df[img_path_field].astype(str)
            else:
                print(f"⚠️ 警告：未找到路径字段 '{img_path_field}'，请检查配置")
        else:
            print(f"⚠️ 警告：未知的路径处理模式 '{img_path_mode}'，使用默认拼接方式")
            if 'origin_object_key' in df.columns:
                base_path = IMG_BASE_PATH if IMG_BASE_PATH.endswith('/') or IMG_BASE_PATH.endswith('\\') else IMG_BASE_PATH + '/'
                df['img_path'] = base_path + df['origin_object_key'].astype(str)
        
        # 生成唯一任务 ID
        task_id = str(uuid.uuid4())
        task_dir = os.path.join(app.config['UPLOAD_FOLDER'], task_id)
        os.makedirs(task_dir, exist_ok=True)
        
        # 保存 CSV
        csv_path = os.path.join(task_dir, 'result.csv')
        df.to_csv(csv_path, index=False, encoding='utf-8')
        
        # 转换为 COCO 格式
        coco_path = os.path.join(task_dir, '_annotations.coco.json')
        try:
            # 获取配置的 id2name
            APP_CONFIG = load_config()
            id2name_config = APP_CONFIG.get('id2name', DEFAULT_CONFIG['id2name'])
            csv2coco(csv_path, coco_path, id2name_config)
        except Exception as e:
            print(f"⚠️ COCO 转换警告: {e}")
        
        # 复制所有图片到导出目录（与COCO文件同一级）
        try:
            for idx, row in df.iterrows():
                img_path = row.get('img_path', '')
                if pd.isna(img_path) or not img_path:
                    continue
                
                # 检查源文件是否存在
                if not os.path.exists(img_path):
                    print(f"⚠️ 图片文件不存在: {img_path}")
                    continue
                
                # 获取图片文件名
                img_name = os.path.basename(img_path)
                # 复制图片到导出目录
                dest_img_path = os.path.join(task_dir, img_name)
                shutil.copy2(img_path, dest_img_path)
        except Exception as e:
            print(f"⚠️ 复制图片警告: {e}")
        
        # 加载COCO数据用于返回标注信息
        coco_data = None
        try:
            with open(coco_path, 'r', encoding='utf-8') as f:
                coco_data = json.load(f)
        except Exception as e:
            print(f"⚠️ 加载COCO数据警告: {e}")
        
        # 准备返回数据（只返回基本信息，不包含完整数据）
        result_data = []
        for idx, row in df.iterrows():
            img_path = row.get('img_path', '')
            img_name = os.path.basename(img_path) if img_path else ''
            
            # 获取该图片的标注信息
            annotations = []
            if coco_data:
                image_id = int(idx)
                for ann in coco_data.get('annotations', []):
                    if ann.get('image_id') == image_id:
                        annotations.append({
                            'bbox': ann.get('bbox', []),
                            'category': ann.get('category', ''),
                            'category_id': ann.get('category_id', 0),
                            'score': ann.get('score', 0)
                        })
            
            result_data.append({
                'id': int(idx),
                'img_name': img_name,
                'img_path': img_path,
                'c_time': str(row.get('c_time', '')),
                'check_status': str(row.get('check_status', '')),
                'detection_result_status': str(row.get('detection_result_status', '')),
                'manual_check_status': str(row.get('manual_check_status', '')),
                'annotations': annotations
            })
        
        return jsonify({
            'success': True,
            'data': result_data,
            'count': len(result_data),
            'task_id': task_id
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/image/<path:filename>')
def get_image(filename):
    """获取图片（从原始路径）"""
    try:
        # 从查询参数获取完整路径
        img_path = request.args.get('path', '')
        if not img_path:
            return jsonify({'error': '图片路径不能为空'}), 400
        
        # 检查文件是否存在
        if not os.path.exists(img_path):
            return jsonify({'error': '图片文件不存在'}), 404
        
        # 返回图片文件
        return send_file(img_path)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/export/<task_id>', methods=['GET', 'POST'])
def export_coco(task_id):
    """导出 COCO 格式文件（包含图片和JSON的ZIP包）"""
    try:
        task_dir = os.path.join(app.config['UPLOAD_FOLDER'], task_id)
        coco_path = os.path.join(task_dir, '_annotations.coco.json')
        csv_path = os.path.join(task_dir, 'result.csv')
        
        if not os.path.exists(coco_path):
            return jsonify({'error': 'COCO 文件不存在'}), 404
        
        # 获取选中的图片索引（如果提供了）
        selected_indices = None
        if request.method == 'POST':
            data = request.get_json() or {}
            selected_indices = data.get('selected_indices', None)
            if selected_indices is not None:
                selected_indices = set(int(idx) for idx in selected_indices)
        
        # 读取原始CSV数据以获取图片文件名映射
        image_filename_map = {}
        if os.path.exists(csv_path):
            try:
                df = pd.read_csv(csv_path, encoding='utf-8')
                for idx, row in df.iterrows():
                    img_path = row.get('img_path', '')
                    if pd.notna(img_path) and img_path:
                        img_name = os.path.basename(str(img_path))
                        image_filename_map[int(idx)] = img_name
            except Exception as e:
                print(f"⚠️ 读取CSV文件警告: {e}")
        
        # 读取COCO数据
        with open(coco_path, 'r', encoding='utf-8') as f:
            coco_data = json.load(f)
        
        # 如果指定了选中的图片，过滤COCO数据
        if selected_indices is not None and len(selected_indices) > 0:
            # 过滤images
            filtered_images = [img for img in coco_data['images'] if img.get('id') in selected_indices]
            selected_image_ids = {img['id'] for img in filtered_images}
            
            # 过滤annotations（只保留选中图片的标注）
            filtered_annotations = [ann for ann in coco_data['annotations'] if ann.get('image_id') in selected_image_ids]
            
            # 创建新的COCO数据
            filtered_coco = {
                'images': filtered_images,
                'annotations': filtered_annotations,
                'categories': coco_data.get('categories', [])
            }
            
            # 临时保存过滤后的COCO文件
            filtered_coco_path = os.path.join(task_dir, '_annotations_filtered.coco.json')
            with open(filtered_coco_path, 'w', encoding='utf-8') as f:
                json.dump(filtered_coco, f, ensure_ascii=False, indent=4)
            coco_path = filtered_coco_path
        
        # 创建临时ZIP文件
        zip_filename = f'coco_export_{task_id}.zip'
        zip_path = os.path.join(app.config['UPLOAD_FOLDER'], zip_filename)
        
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # 添加COCO JSON文件
                zipf.write(coco_path, '_annotations.coco.json')
                
                # 添加图片文件
                image_count = 0
                if selected_indices is not None and len(selected_indices) > 0:
                    # 只添加选中的图片
                    for idx in selected_indices:
                        img_name = image_filename_map.get(idx)
                        if img_name:
                            file_path = os.path.join(task_dir, img_name)
                            if os.path.exists(file_path) and os.path.isfile(file_path):
                                zipf.write(file_path, img_name)
                                image_count += 1
                else:
                    # 添加所有图片文件
                    for filename in os.listdir(task_dir):
                        file_path = os.path.join(task_dir, filename)
                        # 只添加图片文件，跳过JSON和CSV文件
                        if os.path.isfile(file_path) and filename.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp')):
                            zipf.write(file_path, filename)
                            image_count += 1
            
            # 清理临时过滤的COCO文件
            if selected_indices is not None and os.path.exists(filtered_coco_path):
                try:
                    os.remove(filtered_coco_path)
                except:
                    pass
            
            # 返回ZIP文件
            response = send_file(zip_path, as_attachment=True, download_name=f'coco_export_{task_id}.zip', mimetype='application/zip')
            
            # 延迟删除临时ZIP文件（在响应发送后）
            def remove_file():
                try:
                    if os.path.exists(zip_path):
                        os.remove(zip_path)
                except:
                    pass
            
            # 使用Flask的after_request机制会在响应后清理，但这里我们使用线程延迟删除
            import threading
            timer = threading.Timer(60.0, remove_file)  # 60秒后删除
            timer.start()
            
            return response
        except Exception as zip_error:
            # 如果ZIP创建失败，尝试删除临时文件
            try:
                if os.path.exists(zip_path):
                    os.remove(zip_path)
                if selected_indices is not None and os.path.exists(filtered_coco_path):
                    os.remove(filtered_coco_path)
            except:
                pass
            raise zip_error
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/export-csv/<task_id>')
def export_csv(task_id):
    """导出 CSV 文件"""
    try:
        task_dir = os.path.join(app.config['UPLOAD_FOLDER'], task_id)
        csv_path = os.path.join(task_dir, 'result.csv')
        
        if not os.path.exists(csv_path):
            return jsonify({'error': 'CSV 文件不存在'}), 404
        
        return send_file(csv_path, as_attachment=True, download_name='result.csv')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/coco/<task_id>')
def get_coco_data(task_id):
    """获取 COCO 格式数据"""
    try:
        task_dir = os.path.join(app.config['UPLOAD_FOLDER'], task_id)
        coco_path = os.path.join(task_dir, '_annotations.coco.json')
        
        if not os.path.exists(coco_path):
            return jsonify({'error': 'COCO 文件不存在'}), 404
        
        with open(coco_path, 'r', encoding='utf-8') as f:
            coco_data = json.load(f)
        
        return jsonify({'success': True, 'data': coco_data})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050)
