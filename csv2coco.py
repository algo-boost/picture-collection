import os
import sys
import json
import shutil
import pandas as pd


# 默认 id2name 映射（如果未提供配置则使用）
DEFAULT_ID2NAME = {
    0: '其他', 1: '划伤', 2: '压痕', 
    3: '吊紧', 4: '异物外漏', 5: '折痕', 6: '抛线',
    7: '拼接间隙', 8: '水渍', 9: '烫伤', 10: '破损', 
    11: '碰伤', 12: '红标签', 13: '线头', 14: '脏污', 
    15: '褶皱(T型)', 16: '褶皱（重度）', 17: '重跳针'
}

def csv2coco(csv_file, coco_file, id2name=None):
    """
    将csv文件导出为coco格式
    """
    if id2name is None:
        id2name = DEFAULT_ID2NAME
    
    id2name = {int(k): v for k, v in id2name.items()}
    
    name2id = {v: k for k, v in id2name.items()}
    
    df = pd.read_csv(csv_file, encoding="utf-8")
    coco = {
        "images": [],
        "categories": [],
        "annotations": []
    }
    coco["categories"] = [{"id": k, "name": v} for k, v in sorted(id2name.items())]
    for idx, row in df.iterrows():
        img_path = row.get('img_path')
        if pd.isna(img_path):
            continue
        info = {
            "id": idx,
            "file_name": str(os.path.basename(img_path)),
            'position': row.get('position'),
            'product_id': row.get('product_id'),
            'SN': row.get('code'),
            'c_time': row.get('c_time'),
        }
        if row.get('check_status'):
            info['check_status'] = row.get('check_status')
            infer_raw_result = row.get('infer_raw_result')
            # Ensure infer_raw_result is parsed if it is a string
            if isinstance(infer_raw_result, str):
                try:
                    infer_raw_result = json.loads(infer_raw_result)
                except Exception:
                    continue  # skip if parsing fails
            predictions = infer_raw_result.get('predictions', []) if infer_raw_result else []
            for item in predictions:
                points = item.get('points', [])
                if not points:
                    continue
                # Only use the first point for bbox extraction
                point = points[0]
                x = point.get('x')
                y = point.get('y')
                w = point.get('w')
                h = point.get('h')
                if None in (x, y, w, h):
                    continue
                bbox = [x, y, w, h]

                item_name = item.get('name')
                # 如果名称不在映射中，跳过或使用默认值
                if item_name not in name2id:
                    continue
                
                annotation = {
                    "image_id": idx,
                    "category_id": name2id[item_name],
                    "bbox": bbox,
                    'area': w * h,
                    "score": item.get('confidence'),
                    "category": item_name,
                    "defect_type": item.get('defect_type')
                }
                coco["annotations"].append(annotation)   
        coco["images"].append(info)
    with open(coco_file, "w", encoding="utf-8") as f:
        json.dump(coco, f, ensure_ascii=False, indent=4)

def copy_ng_images(coco_file, all_images_dir, ng_images_dir):
    """
    将ng的图片复制到ng_images_dir目录下
    """
    os.makedirs(ng_images_dir, exist_ok=True)
    with open(coco_file, "r", encoding="utf-8") as f:
        coco = json.load(f)
    for image in coco["images"]:
        if image.get('check_status'):
            img_path = image.get('file_name')
            if img_path:
                shutil.copy(os.path.join(all_images_dir, img_path), os.path.join(ng_images_dir, img_path))
    shutil.copy(coco_file, os.path.join(ng_images_dir, "_annotations.coco.json"))


if __name__ == "__main__":
    csv_file  = sys.argv[1]
    coco_file = sys.argv[2]
    csv2coco(csv_file, coco_file, DEFAULT_ID2NAME)
    # copy_ng_images(coco_file, "导出结果/images", "ng_images")