# 图片查询与导出系统

基于 Flask 的 Web 应用，用于查询数据库中的图片数据并导出为 COCO 格式。

## 安装

```bash
pip install -r requirements.txt
```

## 配置

### Web 界面配置

1. 启动应用后，点击右上角的"配置"按钮
2. 填写数据库连接信息（主机、用户名、密码、数据库名）
3. 设置图片基础路径
4. 可选：设置默认 SQL 查询语句
5. 点击"测试连接"验证数据库连接
6. 点击"保存配置"保存设置

配置会保存到 `config.json` 文件，下次启动时自动加载。

### 环境变量配置（可选）

```bash
export DB_HOST=localhost
export DB_USER=root
export DB_PASSWORD=12345678
export DB_DATABASE=vision_backend
export IMG_BASE_PATH=E:/path/to/images/
```

环境变量优先级高于配置文件。

## 运行

```bash
python app.py
```

应用启动在 `http://localhost:5050`

## 使用

1. 输入 SQL 查询语句，使用 `${START_TIME}` 和 `${END_TIME}` 作为时间变量
2. 选择开始时间和结束时间
3. 点击"执行查询"
4. 查看图片：点击图片卡片打开查看器，使用左右箭头键切换
5. 导出数据：点击"导出 COCO"或"导出 CSV"

## 项目结构

```
picture-collection/
├── app.py                 # Flask 应用主文件
├── connect.py             # 数据库连接脚本
├── csv2coco.py            # CSV 转 COCO 格式转换
├── requirements.txt       # Python 依赖
├── config.json            # 配置文件（自动生成）
├── templates/
│   ├── index.html         # 主界面
│   └── config.html        # 配置界面
└── exports/               # 导出文件目录（自动创建）
```

## API 接口

- `POST /api/query` - 执行 SQL 查询
- `GET /api/config` - 获取配置
- `POST /api/config` - 保存配置
- `POST /api/config/test-connection` - 测试数据库连接
- `GET /api/image/<filename>?path=<full_path>` - 获取图片
- `GET /api/export/<task_id>` - 导出 COCO 文件
- `GET /api/export-csv/<task_id>` - 导出 CSV 文件

## 注意事项

- SQL 查询必须包含 `origin_object_key` 字段才能生成图片路径
- 配置文件包含敏感信息，注意保护
- 导出的文件保存在 `exports/` 目录，每个查询任务有独立文件夹
