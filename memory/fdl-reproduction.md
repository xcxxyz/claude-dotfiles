---
name: fdl-reproduction
description: CVPR 2024 FDL论文复现 — 频域分布损失图像增强
metadata: 
  node_type: memory
  type: project
  originSessionId: 2b311dec-eaf8-4bdd-bb84-ba0b01f0a0fb
---

## 内容
- 复现CVPR 2024论文 "Misalignment-Robust Frequency Distribution Loss for Image Transformation"
- `FDL/` — 官方pip包 `fdl-pytorch` (核心FDL_loss类)
- `FDL_Reproduction/` — 完整复现pipeline: `run_pipeline.py` 训练U-Net + 多种loss对比(L1/L2/Perceptual/LPIPS/FDL) + 可视化
- DPED数据集实验 + FDL鲁棒性演示

**Why:** 课程论文复现/图像处理研究
