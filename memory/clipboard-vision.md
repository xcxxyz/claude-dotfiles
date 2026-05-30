---
name: clipboard-vision
description: 剪切板识图 — 截图后调用阿里DashScope视觉模型描述图片内容
metadata: 
  node_type: memory
  type: reference
  originSessionId: 2b311dec-eaf8-4bdd-bb84-ba0b01f0a0fb
---

## 功能
截图 → `python ~/clipboard-vision.py` → 阿里 DashScope API (qwen-vl-plus) → 模型描述

## 用法
```bash
python ~/clipboard-vision.py                    # 默认：请详细描述这张图片的内容
python ~/clipboard-vision.py "这段代码是什么语言"  # 自定义提问
```

## 技术
- 平台: 阿里云百炼 DashScope (dashscope.aliyuncs.com)
- 模型: qwen-vl-plus
- 剪切板读取: PIL ImageGrab.grabclipboard()
- 图片编码: JPEG base64
