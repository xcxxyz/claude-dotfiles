## 图片处理规范
禁止使用 `read` 工具读取任何图片文件（如 .png, .jpg, .jpeg）
强制使用 image-analysis 这个 skill 来读取图片
当模型返回不支持直接读取图片时，自动调用 image-analysis 这个 skill 来读取图片

## 编辑限制（最高优先级）
**禁止使用 Write 工具重写 settings.json。**
只能使用 Edit 工具修改 settings.json 的单个字段。
API key 已隔离到 settings.local.json，Write settings.json 不会覆盖 API key，但可能触发 Cursor 代理接管。
违反此规则 → 用户需要重新登录。

## 搜索规范（最高优先级）
**禁止使用内置 WebSearch 工具进行网页搜索。**
所有搜索操作必须使用自部署深度搜索系统：
```
/d/temp/dlc-env/Scripts/python C:/temp/deep-search.py "搜索内容" [结果数]
```
搜索完成后：用 Read 工具读入 `C:/temp/deep_search_result.md`，再基于内容回答。
前置条件：SearXNG Docker 容器必须运行（`docker ps` 检查 searxng）。如容器未运行，先启动后再搜索。
