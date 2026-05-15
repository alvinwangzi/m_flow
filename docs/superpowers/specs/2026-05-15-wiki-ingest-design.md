# Wiki 导入设计

## 摘要

新增一条独立的 Karpathy 风格 Wiki 导入路径，用于书籍、PDF、笔记和价值较低或质量不稳定的资料。该路径默认不运行完整的 M-flow 图谱构建流程，而是快速生成可阅读、可搜索的 Markdown 知识层。用户可以在之后选择将某个 Wiki 集合升级为现有的 M-flow 精细记忆流程。

这不是对 `add()` 或 `memorize()` 的替代，而是一种成本和质量取舍不同的导入模式。

## 目标

- 为长书、PDF、笔记和低置信度资料提供一个更快的默认导入路径。
- 产出可立即使用的 Wiki 页面，包括索引、来源摘要、章节页和概念页。
- 让 Wiki 页面可以通过轻量索引被搜索。
- 让用户自行决定某个 Wiki 集合是否值得升级为完整 M-flow 记忆。
- 保持现有 `ingest`、`add`、`memorize` 行为稳定。

## 非目标

- 不重写现有 M-flow `memorize_pipeline`。
- 不要求每个 Wiki 页面都转换成 Episode、Facet、Entity 或 FacetPoint。
- 第一版不做完整 Wiki 编辑器或多人协作能力。
- 第一版不追求完美章节识别；标题启发式加兜底分段即可。

## 方案

新增独立 API 模块 `m_flow/api/v1/wiki/`，而不是扩展 `/api/v1/ingest`。

第一版暴露以下接口：

- `POST /api/v1/wiki/ingest`：JSON 文本导入
- `POST /api/v1/wiki/ingest/upload`：multipart 文件上传导入
- `GET /api/v1/wiki/collections/{id}`：获取 Wiki 集合元信息
- `GET /api/v1/wiki/collections/{id}/pages`：列出生成的页面
- `GET /api/v1/wiki/pages/{id}`：获取单个页面
- `POST /api/v1/wiki/collections/{id}/upgrade`：对源数据集后台运行现有 `memorize()`

Wiki router 与当前 ingest router 保持分离，避免在 `m_flow/api/v1/ingest/ingest.py` 中继续增加分支复杂度。

两个导入接口都接受 `upgrade_after_ingest` 布尔参数。为 `false` 时只生成 Wiki 页面；为 `true` 时，在 Wiki 生成开始或完成后返回，并在后台触发现有 M-flow 深度记忆升级。

## 数据模型

新增两个关系型模型。

`WikiCollection`

- `id`：UUID
- `dataset_id`：UUID
- `source_data_id`：UUID，多来源集合时可为空
- `title`：字符串
- `status`：`processing | ready | failed | upgrading | upgraded`
- `error_message`：字符串，可为空
- `created_at`、`updated_at`
- `owner_id`、`tenant_id`

`WikiPage`

- `id`：UUID
- `collection_id`：UUID
- `path`：字符串，例如 `index.md`、`summary.md`、`chapters/chapter-01.md`
- `file_uri`：字符串，Markdown 正文在硬盘上的文件地址
- `title`：字符串
- `content_hash`：字符串
- `page_type`：`index | summary | chapter | concept`
- `source_hash`：字符串，表示生成该页面所用源片段的 hash
- `excerpt`：字符串，可为空，用于列表页和搜索结果预览
- `created_at`、`updated_at`

Markdown 正文必须存放在硬盘文件系统中，不直接写入数据库。关系数据库只保存页面元信息、文件路径、hash、类型、标题和短摘要。

默认目录结构：

```text
<DATA_ROOT_DIRECTORY>/wiki/
  <collection_id>/
    index.md
    summary.md
    chapters/
      chapter-01.md
    concepts/
      concept-name.md
```

第一版使用现有本地文件存储配置写入硬盘。后续如果需要支持 S3 或对象存储，可以沿用 storage abstraction，但默认实现必须是硬盘 Markdown 文件。

## 流程

Wiki 导入流程如下：

1. 通过现有 `add()` 保存上传源数据，保留原始来源、数据集和权限关系。
2. 解析已保存的源文件，尽量复用现有 loader 基础设施抽取文本。
3. 将文本拆分为书籍段落：
   - 优先使用检测到的标题或目录。
   - 对结构不清晰的文本，退化为较大的 token 窗口分段。
4. 生成或更新 Markdown 页面：
   - `index.md`：目录和页面链接
   - `summary.md`：整本资料摘要
   - `chapters/*.md`：章节或大段落摘要和关键点
   - `concepts/*.md`：高频且高价值的人物、术语、组织和思想
5. 对 section 和 page 计算 hash，未变化的片段跳过重新生成。
6. 将 Markdown 正文写入硬盘上的 Wiki 目录。
7. 写入或更新 `WikiPage` 元信息，包括 `file_uri`、`content_hash`、`source_hash` 和 `excerpt`。
8. 为页面建立轻量搜索索引。

`wiki` 模式不会运行完整 M-flow 流程。升级接口会对集合所在数据集调用现有 `memorize(datasets=[...], run_in_background=True, ...)`。

## 搜索

第一版搜索目标是让 Wiki 页面快速可用。采用分阶段实现：

1. 先用 SQL 查询 `WikiPage.title`、`WikiPage.path` 和 `WikiPage.excerpt`，再按候选页面读取硬盘 Markdown 文件做大小写不敏感匹配。
2. 功能稳定后，再为 Wiki 页面增加向量索引。

查询界面需要把 Wiki 结果和图谱记忆结果区分展示，让用户理解二者精度和来源不同。

## 前端

在导入页面增加处理模式选择：

- `Wiki 快速模式`：默认选项，适合书籍和探索性资料。
- `M-flow 精细记忆`：适合高价值资料，需要图谱构建和关系推理。
- `Wiki + 后台精细记忆`：先快速可读可搜，再自动后台升级。

Wiki 集合完成后，页面提供：

- 打开 Wiki
- 搜索 Wiki
- 升级为 M-flow 记忆
- 查看升级状态

前端文案需要明确说明取舍：Wiki 模式更快、更省；精细记忆更慢，但结构更丰富。

## 错误处理

- 如果原始 `add()` 失败，直接返回错误，不创建 Wiki 集合。
- 如果源数据 add 成功但 Wiki 生成失败，将 `WikiCollection.status` 标记为 `failed`，并保留源数据集。
- 如果单个 section 生成失败，在集合元信息中记录页面级警告，并继续处理其他页面。
- 如果升级失败，Wiki 仍保持可用；集合状态回到 `ready`，并记录升级错误信息。

## 权限

Wiki 集合和页面继承数据集所有权。所有 collection/page 查询都必须按当前用户有权限的数据集过滤，或匹配 `owner_id` / `tenant_id`，遵循现有权限模型。

## 测试

后端测试：

- Wiki 导入会创建 collection 和 pages，并且不会调用 `memorize()`。
- Wiki 导入会把 Markdown 正文写入硬盘，并且数据库中只保存 `file_uri` 等元信息。
- `upgrade_after_ingest` 或手动升级会以 `run_in_background=True` 触发 `memorize()`。
- 重复导入未变化 section 时，通过 hash 跳过页面重生成。
- 页面生成失败时，集合被标记为失败或部分完成，且不会破坏源数据。
- 权限检查阻止用户读取他人的 Wiki 集合。

前端测试：

- 处理模式选择器会发送正确 API 请求。
- Wiki 结果页会列出页面并提供升级动作。
- 升级状态与 Wiki 可用状态分开展示。

## 分阶段落地

阶段 1：

- 后端模型、router、基础 pipeline、硬盘 Markdown 写入、轻量文件搜索、最小前端模式选择器。

阶段 2：

- 更好的章节识别、概念页生成、页面级 hash 复用。

阶段 3：

- Wiki 页面向量索引，以及与现有搜索结果的统一展示。

阶段 4：

- 导入流程中可选自动后台深度记忆升级。

## 初始决策

- 章节检测第一版采用简单标题启发式和兜底分段。
- Markdown 正文第一版必须存在硬盘上，数据库只保存元信息和文件路径。
- 第一版 Wiki 搜索可以先用 SQL 元信息过滤加硬盘文件内容匹配；初始版本不要求向量搜索。
