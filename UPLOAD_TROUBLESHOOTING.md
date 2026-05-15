# 文件上传失败排查指南

## 问题现象
- 前端上传 4 个文件失败
- 后端返回 `409 Conflict` 错误
- 日志显示 `step=Failed`

## 已实施的修复

### 1. 改进错误响应 (已完成)
**文件**: `m_flow/api/v1/add/routers/get_add_router.py`

**变更**:
- 将 `RunFailed` 的状态码从非标准的 `420` 改为 `500`
- 增加详细的错误信息，包括:
  - `error`: 错误类型描述
  - `details`: 具体错误信息
  - `workflow_run_id`: 可用于追踪的执行 ID
- 增加异常日志记录 (`_log.exception`)

### 2. 下一步：查看详细错误信息

重启后端服务后，再次上传文件，你应该会看到：

**前端错误响应**:
```json
{
  "error": "Pipeline execution failed",
  "details": "具体错误原因",
  "workflow_run_id": "xxx-xxx-xxx"
}
```

**后端日志**:
```
[add] Pipeline failed: <详细错误信息>
[add] Unexpected error: <异常堆栈>
```

## 常见失败原因及解决方案

### 原因 1: LLM API 调用失败
**症状**: 错误信息包含 "LLM", "API key", "OpenAI", "timeout" 等关键词

**解决方案**:
1. 检查 `.env` 文件中的 LLM 配置:
   ```bash
   LLM_API_KEY=your_api_key_here
   LLM_PROVIDER=openai  # 或 anthropic, azure 等
   LLM_MODEL=gpt-4o     # 或你的模型
   ```

2. 验证 API Key 是否有效:
   ```bash
   curl https://api.openai.com/v1/chat/completions \
     -H "Authorization: Bearer $LLM_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model":"gpt-4o","messages":[{"role":"user","content":"test"}]}'
   ```

### 原因 2: SQLite 数据库锁定
**症状**: 日志包含 "database is locked", "OperationalError"

**解决方案**:
1. **串行上传**（临时方案）: 一次只上传一个文件，等待完成后再上传下一个

2. **切换到 PostgreSQL**（推荐方案）:
   ```bash
   # .env 文件
   DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/mflow
   GRAPH_DATABASE_PROVIDER=neo4j  # 或其他图数据库
   ```

3. **增加重试机制**（代码层面）:
   SQLite 并发限制已在 `db_concurrency.py` 中设置为 1，但仍可能出现锁定

### 原因 3: 文件格式问题
**症状**: 错误信息包含 "parse", "decode", "unsupported format"

**解决方案**:
1. 检查上传的文件格式是否支持:
   - 文本: `.txt`, `.md`, `.csv`
   - 文档: `.pdf`, `.docx`
   - 其他: 查看 `m_flow/shared/loaders/` 下的 loader

2. 尝试上传一个简单的 `.txt` 文件测试

3. 检查文件是否损坏或加密

### 原因 4: 内存不足
**症状**: 错误信息包含 "MemoryError", "OOM", "killed"

**解决方案**:
1. 减小批量大小:
   ```bash
   # 在代码或配置中设置
   items_per_batch=5  # 默认 20
   ```

2. 增加系统内存或关闭其他应用

### 原因 5: Pipeline 任务执行失败
**症状**: 错误信息包含具体的任务名称，如 "ingest_data", "resolve_data_directories"

**解决方案**:
查看完整的错误堆栈，定位到具体的任务阶段

## 调试步骤

### 步骤 1: 重启后端服务
```bash
# Windows PowerShell
cd e:\AIProject\m_flow
uv run python -m m_flow.api.client
```

### 步骤 2: 启用详细日志
在 `.env` 文件中添加:
```bash
LOG_LEVEL=DEBUG
```

### 步骤 3: 重新上传文件
观察后端控制台输出，查找:
```
[add] Pipeline failed: <错误详情>
```

### 步骤 4: 检查数据库状态
```bash
# 查看 pipeline 运行状态
uv run python -c "
import asyncio
from m_flow.adapters.relational import get_db_adapter
from m_flow.pipeline.models import WorkflowRun

async def check():
    engine = get_db_adapter()
    async with engine.get_async_session() as session:
        from sqlalchemy import select
        stmt = select(WorkflowRun).order_by(WorkflowRun.created_at.desc()).limit(5)
        result = await session.execute(stmt)
        for run in result.scalars().all():
            print(f'Run: {run.workflow_run_id}')
            print(f'Status: {run.status}')
            print(f'Detail: {run.run_detail}')
            print('---')

asyncio.run(check())
"
```

### 步骤 5: 单文件测试
尝试只上传 1 个文件，确认是否是并发问题

## 快速诊断脚本

创建一个诊断脚本来检查常见问题:

```python
# diagnose_upload.py
import os
from dotenv import load_dotenv

load_dotenv()

print("=== M-Flow Upload Diagnosis ===\n")

# 1. Check LLM config
print("1. LLM Configuration:")
print(f"   LLM_PROVIDER: {os.getenv('LLM_PROVIDER', 'NOT SET')}")
print(f"   LLM_MODEL: {os.getenv('LLM_MODEL', 'NOT SET')}")
print(f"   LLM_API_KEY: {'SET' if os.getenv('LLM_API_KEY') else 'NOT SET'}")

# 2. Check database
print("\n2. Database Configuration:")
db_url = os.getenv('DATABASE_URL', 'sqlite')
print(f"   DATABASE_URL: {db_url}")
if 'sqlite' in db_url.lower():
    print("   ⚠️  Using SQLite - limited concurrency support")

# 3. Check environment
print("\n3. Environment:")
print(f"   Python: {os.sys.version}")
print(f"   Platform: {os.sys.platform}")

# 4. Test LLM connection (optional)
print("\n4. LLM Connection Test:")
api_key = os.getenv('LLM_API_KEY')
if api_key:
    print("   API key is set, but connection test not implemented")
else:
    print("   ❌ LLM_API_KEY not set - this will cause pipeline failures")

print("\n=== Diagnosis Complete ===")
print("\nNext steps:")
print("1. If LLM_API_KEY is not set, add it to .env")
print("2. Restart the backend service")
#3. Try uploading a single small .txt file")
print("4. Check backend logs for detailed error messages")
```

运行诊断:
```bash
uv run python diagnose_upload.py
```

## 联系支持

如果以上步骤无法解决问题，请提供:
1. 完整的后端日志（从启动到失败）
2. `.env` 文件内容（**删除敏感信息**如 API keys）
3. 上传的文件类型和大小
4. 前端显示的错误信息

## 相关代码文件

- 路由器: `m_flow/api/v1/add/routers/get_add_router.py`
- Pipeline: `m_flow/pipeline/operations/run_tasks.py`
- 并发控制: `m_flow/pipeline/operations/db_concurrency.py`
- 错误记录: `m_flow/pipeline/operations/record_run_failure.py`
