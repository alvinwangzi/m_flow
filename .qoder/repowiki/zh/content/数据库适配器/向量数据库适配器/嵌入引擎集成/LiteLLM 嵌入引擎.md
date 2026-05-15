# LiteLLM 嵌入引擎

<cite>
**本文档引用的文件**
- [LiteLLMEmbeddingEngine.py](file://m_flow/adapters/vector/embeddings/LiteLLMEmbeddingEngine.py)
- [EmbeddingEngine.py](file://m_flow/adapters/vector/embeddings/EmbeddingEngine.py)
- [get_embedding_engine.py](file://m_flow/adapters/vector/embeddings/get_embedding_engine.py)
- [config.py](file://m_flow/adapters/vector/embeddings/config.py)
- [rate_limiting.py](file://m_flow/shared/rate_limiting.py)
- [save_embedding_config.py](file://m_flow/config/settings/save_embedding_config.py)
- [EmbeddingConfigStep.tsx](file://m_flow-frontend/src/components/setup/ConfigWizard/steps/EmbeddingConfigStep.tsx)
- [EmbeddingSettings.tsx](file://m_flow-frontend/src/components/settings/EmbeddingSettings.tsx)
- [FastembedEmbeddingEngine.py](file://m_flow/adapters/vector/embeddings/FastembedEmbeddingEngine.py)
- [OllamaEmbeddingEngine.py](file://m_flow/adapters/vector/embeddings/OllamaEmbeddingEngine.py)
- [test_embedding_config_custom_provider.py](file://m_flow/tests/unit/infrastructure/vector/embeddings/test_embedding_config_custom_provider.py)
</cite>

## 更新摘要
**所做更改**
- 更新了批量处理能力章节，详细说明了可配置的批量大小和智能分块功能
- 新增了批量处理性能优化和吞吐量提升的相关内容
- 更新了配置指南，强调批量大小对性能的影响
- 增强了性能监控和成本控制的最佳实践部分

## 目录
1. [简介](#简介)
2. [项目结构](#项目结构)
3. [核心组件](#核心组件)
4. [架构总览](#架构总览)
5. [详细组件分析](#详细组件分析)
6. [批量处理能力增强](#批量处理能力增强)
7. [依赖关系分析](#依赖关系分析)
8. [性能考量](#性能考量)
9. [故障排查指南](#故障排查指南)
10. [结论](#结论)
11. [附录](#附录)

## 简介
本文件面向 LiteLLM 嵌入引擎的技术文档，系统性阐述其多提供商路由能力与统一嵌入接口设计。该引擎支持 OpenAI、Azure、以及通过 LiteLLM 兼容层接入的其他提供商（如自定义兼容端点），并提供统一的异步嵌入接口、上下文窗口溢出处理、批量分片与池化、速率限制、重试机制与错误处理。同时给出配置指南、使用示例与最佳实践，帮助在不同提供商之间进行智能路由与成本优化。

**更新** 本版本重点增强了批量处理能力，包括可配置的批量大小和智能分块功能，显著提高了大数集嵌入生成的资源利用率和吞吐量。

## 项目结构
LiteLLM 嵌入引擎位于向量适配层的嵌入子模块中，采用协议驱动的适配器模式，结合工厂方法与缓存机制，按配置动态构建具体引擎实例。前端提供配置向导与设置页面，后端提供配置持久化与运行时更新能力。

```mermaid
graph TB
subgraph "嵌入引擎适配层"
A["EmbeddingEngine 协议"]
B["LiteLLMEmbeddingEngine"]
C["FastembedEmbeddingEngine"]
D["OllamaEmbeddingEngine"]
E["get_embedding_engine 工厂"]
F["config 配置"]
end
subgraph "共享组件"
G["rate_limiting 速率限制"]
H["save_embedding_config 配置持久化"]
end
subgraph "前端"
I["EmbeddingConfigStep 配置向导"]
J["EmbeddingSettings 设置页"]
end
A --> B
A --> C
A --> D
E --> B
E --> C
E --> D
B --> G
C --> G
D --> G
H --> F
I --> F
J --> F
```

**图表来源**
- [EmbeddingEngine.py:14-63](file://m_flow/adapters/vector/embeddings/EmbeddingEngine.py#L14-L63)
- [LiteLLMEmbeddingEngine.py:37-178](file://m_flow/adapters/vector/embeddings/LiteLLMEmbeddingEngine.py#L37-L178)
- [get_embedding_engine.py:16-99](file://m_flow/adapters/vector/embeddings/get_embedding_engine.py#L16-L99)
- [config.py:16-68](file://m_flow/adapters/vector/embeddings/config.py#L16-L68)
- [rate_limiting.py:23-31](file://m_flow/shared/rate_limiting.py#L23-L31)
- [save_embedding_config.py:33-81](file://m_flow/config/settings/save_embedding_config.py#L33-L81)
- [EmbeddingConfigStep.tsx:45-83](file://m_flow-frontend/src/components/setup/ConfigWizard/steps/EmbeddingConfigStep.tsx#L45-L83)
- [EmbeddingSettings.tsx:38-42](file://m_flow-frontend/src/components/settings/EmbeddingSettings.tsx#L38-L42)

**章节来源**
- [EmbeddingEngine.py:1-64](file://m_flow/adapters/vector/embeddings/EmbeddingEngine.py#L1-L64)
- [get_embedding_engine.py:1-100](file://m_flow/adapters/vector/embeddings/get_embedding_engine.py#L1-L100)
- [config.py:1-69](file://m_flow/adapters/vector/embeddings/config.py#L1-L69)

## 核心组件
- 统一协议接口：定义嵌入引擎必须实现的方法契约，确保不同提供商适配器的一致行为。
- LiteLLM 引擎：基于 LiteLLM 的异步嵌入调用，支持 OpenAI/Azure 等提供商，并内置上下文溢出处理与重试。
- 工厂与缓存：根据配置动态构建引擎实例，使用 LRU 缓存避免重复连接。
- 配置系统：集中管理提供商、模型、维度、端点、密钥、批次大小等参数。
- 速率限制：对嵌入请求进行统一限流，可按配置启用或禁用。
- 前端配置：提供可视化配置向导与设置页，支持 OpenAI、Azure、Ollama、FastEmbed 等提供商。

**章节来源**
- [EmbeddingEngine.py:14-63](file://m_flow/adapters/vector/embeddings/EmbeddingEngine.py#L14-L63)
- [LiteLLMEmbeddingEngine.py:37-178](file://m_flow/adapters/vector/embeddings/LiteLLMEmbeddingEngine.py#L37-L178)
- [get_embedding_engine.py:16-99](file://m_flow/adapters/vector/embeddings/get_embedding_engine.py#L16-L99)
- [config.py:16-68](file://m_flow/adapters/vector/embeddings/config.py#L16-L68)
- [rate_limiting.py:23-31](file://m_flow/shared/rate_limiting.py#L23-L31)
- [EmbeddingConfigStep.tsx:45-83](file://m_flow-frontend/src/components/setup/ConfigWizard/steps/EmbeddingConfigStep.tsx#L45-L83)
- [EmbeddingSettings.tsx:38-42](file://m_flow-frontend/src/components/settings/EmbeddingSettings.tsx#L38-L42)

## 架构总览
LiteLLM 嵌入引擎通过工厂方法按配置选择具体提供商实现，统一对外暴露异步嵌入接口。引擎内部使用速率限制上下文、指数退避重试与异常分类处理，针对上下文窗口溢出进行分片与池化，保证稳定性与吞吐。

```mermaid
sequenceDiagram
participant Caller as "调用方"
participant Factory as "get_embedding_engine"
participant Engine as "LiteLLMEmbeddingEngine"
participant Rate as "embedding_rate_limiter_context_manager"
participant LiteLLM as "LiteLLM 异步嵌入"
Caller->>Factory : 获取嵌入引擎实例
Factory-->>Caller : 返回缓存的引擎
Caller->>Engine : embed_text(text[])
Engine->>Rate : 进入限流上下文
Rate-->>Engine : 允许执行
Engine->>LiteLLM : aembedding(model, input, api_key, api_base, api_version)
LiteLLM-->>Engine : 返回向量数据
Engine-->>Caller : 返回向量列表
```

**图表来源**
- [get_embedding_engine.py:16-38](file://m_flow/adapters/vector/embeddings/get_embedding_engine.py#L16-L38)
- [LiteLLMEmbeddingEngine.py:85-109](file://m_flow/adapters/vector/embeddings/LiteLLMEmbeddingEngine.py#L85-L109)
- [rate_limiting.py:56-58](file://m_flow/shared/rate_limiting.py#L56-L58)

## 详细组件分析

### 统一嵌入接口协议
- 方法契约：定义 embed_text、get_vector_size、get_batch_size 三个方法，作为所有嵌入适配器的结构化协议。
- 设计要点：使用运行时协议检查，无需显式继承，降低耦合；方法签名严格约束返回类型与异常语义。

**章节来源**
- [EmbeddingEngine.py:14-63](file://m_flow/adapters/vector/embeddings/EmbeddingEngine.py#L14-L63)

### LiteLLM 嵌入引擎
- 引擎职责：封装 LiteLLM 的异步嵌入调用，支持 OpenAI、Azure 与自定义兼容端点；负责上下文溢出处理、批量分片与池化、重试与错误分类。
- 关键特性：
  - 批量处理：按 batch_size 分批发送请求，减少单次调用开销。
  - 上下文溢出处理：当输入文本过大导致上下文超限时，自动递归分片或重叠池化，保证结果一致性。
  - 重试机制：对非鉴权类错误采用指数退避+抖动重试，最大时长受限，避免雪崩。
  - 令牌计数：根据提供商自动选择合适的分词器，用于预处理与长度估算。
  - 模拟模式：通过环境变量开启，便于测试与离线开发。

```mermaid
flowchart TD
Start(["进入 embed_text"]) --> CheckMock{"是否启用模拟模式?"}
CheckMock --> |是| ReturnZero["返回零向量占位"]
CheckMock --> |否| InitBatch["计算批次大小"]
InitBatch --> LoopBatches{"遍历批次"}
LoopBatches --> EnterLimiter["进入嵌入限流上下文"]
EnterLimiter --> CallLiteLLM["调用 litellm.aembedding(...)"]
CallLiteLLM --> Collect["收集向量"]
Collect --> NextBatch{"还有批次?"}
NextBatch --> |是| LoopBatches
NextBatch --> |否| ReturnVecs["返回完整向量列表"]
CallLiteLLM --> Overflow{"ContextWindowExceeded?"}
Overflow --> |是| HandleOverflow["处理上下文溢出"]
HandleOverflow --> ReturnVecs
CallLiteLLM --> OtherErr{"其他错误?"}
OtherErr --> |是| Raise["抛出 EmbeddingException"]
OtherErr --> |否| ReturnVecs
```

**图表来源**
- [LiteLLMEmbeddingEngine.py:85-143](file://m_flow/adapters/vector/embeddings/LiteLLMEmbeddingEngine.py#L85-L143)

**章节来源**
- [LiteLLMEmbeddingEngine.py:37-178](file://m_flow/adapters/vector/embeddings/LiteLLMEmbeddingEngine.py#L37-L178)

### 工厂与缓存机制
- 工厂函数：根据配置选择提供商，支持 fastembed、ollama 与 LiteLLM 三大类；对 LiteLLM 类别进一步区分 openai、azure 与其他自定义兼容端点。
- API 密钥选择：优先使用嵌入专用密钥，若未配置则回退到 LLM 配置中的密钥；当提供商为 custom 时可使用独立密钥策略。
- 实例缓存：使用 LRU 缓存避免重复初始化，降低连接与初始化成本。

```mermaid
classDiagram
class get_embedding_engine {
+get_embedding_engine() EmbeddingEngine
}
class _build_engine {
+_build_engine(provider, model, dimensions, max_tokens, endpoint, api_key, api_version, batch_size, hf_tokenizer, llm_api_key, llm_provider) EmbeddingEngine
}
class LiteLLMEmbeddingEngine
class FastembedEmbeddingEngine
class OllamaEmbeddingEngine
get_embedding_engine --> _build_engine : "调用"
_build_engine --> LiteLLMEmbeddingEngine : "openai/azure/custom"
_build_engine --> FastembedEmbeddingEngine : "fastembed"
_build_engine --> OllamaEmbeddingEngine : "ollama"
```

**图表来源**
- [get_embedding_engine.py:16-99](file://m_flow/adapters/vector/embeddings/get_embedding_engine.py#L16-L99)
- [LiteLLMEmbeddingEngine.py:37-66](file://m_flow/adapters/vector/embeddings/LiteLLMEmbeddingEngine.py#L37-L66)
- [FastembedEmbeddingEngine.py:35-70](file://m_flow/adapters/vector/embeddings/FastembedEmbeddingEngine.py#L35-L70)
- [OllamaEmbeddingEngine.py:38-77](file://m_flow/adapters/vector/embeddings/OllamaEmbeddingEngine.py#L38-L77)

**章节来源**
- [get_embedding_engine.py:16-99](file://m_flow/adapters/vector/embeddings/get_embedding_engine.py#L16-L99)

### 配置系统与持久化
- 配置项：提供商、模型、维度、端点、API 密钥、API 版本、最大完成令牌、批次大小、HuggingFace 分词器名称等。
- 默认值：未指定时提供合理默认；批次大小未指定时默认为 36。
- 持久化：通过设置页或向导更新配置时，可选择是否写入 .env 文件，保护敏感信息（密钥字段支持掩码占位）。

```mermaid
flowchart TD
UI["前端设置/向导"] --> DTO["EmbeddingConfigDTO"]
DTO --> Save["save_embedding_config(dto, persist)"]
Save --> UpdateActive["更新活动配置"]
Save --> Persist[".env 写入(可选)"]
UpdateActive --> Reload["后续 get_embedding_engine 使用新配置"]
```

**图表来源**
- [save_embedding_config.py:33-81](file://m_flow/config/settings/save_embedding_config.py#L33-L81)
- [config.py:16-68](file://m_flow/adapters/vector/embeddings/config.py#L16-L68)

**章节来源**
- [config.py:16-68](file://m_flow/adapters/vector/embeddings/config.py#L16-L68)
- [save_embedding_config.py:33-81](file://m_flow/config/settings/save_embedding_config.py#L33-L81)
- [EmbeddingConfigStep.tsx:45-83](file://m_flow-frontend/src/components/setup/ConfigWizard/steps/EmbeddingConfigStep.tsx#L45-L83)
- [EmbeddingSettings.tsx:38-42](file://m_flow-frontend/src/components/settings/EmbeddingSettings.tsx#L38-L42)

### 速率限制与重试机制
- 速率限制：通过嵌入专用限流器对并发请求进行节流，支持按配置开关与区间调整。
- 重试策略：对非鉴权类错误（如 400/404）采用指数退避+抖动重试，最大等待时间受限；对鉴权/未找到等错误直接抛出业务异常。
- 超时与安全：HTTP 请求使用安全 SSL 上下文与超时控制，避免阻塞与资源泄露。

**章节来源**
- [rate_limiting.py:23-31](file://m_flow/shared/rate_limiting.py#L23-L31)
- [LiteLLMEmbeddingEngine.py:72-84](file://m_flow/adapters/vector/embeddings/LiteLLMEmbeddingEngine.py#L72-L84)
- [OllamaEmbeddingEngine.py:101-113](file://m_flow/adapters/vector/embeddings/OllamaEmbeddingEngine.py#L101-L113)

### 上下文窗口溢出处理
- 批量溢出：当一批文本整体超过上下文限制时，递归将批次拆半，分别嵌入后再合并。
- 单条溢出：当单个字符串过长时，按三分之一重叠切分，分别嵌入后做向量平均池化，提升语义一致性。
- 边界校验：空输入直接抛出上下文溢出异常，防止无效处理。

**章节来源**
- [LiteLLMEmbeddingEngine.py:118-143](file://m_flow/adapters/vector/embeddings/LiteLLMEmbeddingEngine.py#L118-L143)

### 分词器选择策略
- OpenAI/Azure：优先使用 TikToken 分词器；若模型不在注册表内则回退到通用 cl100k_base。
- Gemini：使用 TikToken 分词器。
- Mistral：使用 Mistral 分词器。
- 其他/Hugging Face：尝试 HuggingFace 分词器，失败则回退到 TikToken。

**章节来源**
- [LiteLLMEmbeddingEngine.py:151-177](file://m_flow/adapters/vector/embeddings/LiteLLMEmbeddingEngine.py#L151-L177)

## 批量处理能力增强

### 可配置批量大小
LiteLLM 嵌入引擎引入了可配置的批量大小功能，通过 `batch_size` 参数控制每次嵌入调用处理的文本数量。该功能显著提升了大数集嵌入生成的资源利用率和吞吐量。

- **默认批量大小**：引擎初始化时设置默认批量大小为 100，可根据具体需求进行调整
- **动态计算**：在 `embed_text` 方法中，批量大小通过 `max(1, int(self.batch_size or len(text) or 1))` 动态计算，确保至少处理一个批次
- **分批处理**：使用 `for start in range(0, len(text), batch_size)` 实现智能分批，支持任意规模的文本数组

### 智能分块功能
引擎提供了智能分块功能，能够根据上下文窗口限制自动处理超大文本：

- **批量级分块**：当整个批次超出上下文限制时，自动将批次拆分为两半，递归处理后合并结果
- **单文本分块**：对于单个超长文本，采用三分之一重叠切分策略，分别嵌入后进行向量池化
- **性能优化**：使用 `asyncio.gather` 并行处理分块，提升整体处理效率

### 吞吐量提升机制
批量处理能力的增强带来了显著的吞吐量提升：

- **减少 API 调用次数**：通过批量处理减少网络往返和 API 调用开销
- **优化资源利用**：更大的批次大小充分利用 GPU/CPU 资源，提高计算效率
- **降低延迟**：减少 API 调用频率，降低整体处理延迟
- **成本优化**：在某些提供商上，批量处理可以减少请求成本

```mermaid
flowchart TD
Start(["开始批量处理"]) --> CalcBatch["计算批量大小<br/>max(1, int(self.batch_size or len(text) or 1))"]
CalcBatch --> LoopBatches["遍历批次<br/>for start in range(0, len(text), batch_size)"]
LoopBatches --> CheckSize{"批次大小 > 0?"}
CheckSize --> |是| EnterLimiter["进入嵌入限流上下文"]
EnterLimiter --> CallLiteLLM["调用 litellm.aembedding()<br/>批量处理当前批次"]
CallLiteLLM --> Collect["收集向量结果"]
Collect --> NextBatch{"还有批次?"}
NextBatch --> |是| LoopBatches
NextBatch --> |否| ReturnVecs["返回完整向量列表"]
CheckSize --> |否| HandleOverflow["处理上下文溢出"]
HandleOverflow --> SplitBatch["递归拆分批次"]
SplitBatch --> ReturnVecs
```

**图表来源**
- [LiteLLMEmbeddingEngine.py:95-109](file://m_flow/adapters/vector/embeddings/LiteLLMEmbeddingEngine.py#L95-L109)

**章节来源**
- [LiteLLMEmbeddingEngine.py:47-66](file://m_flow/adapters/vector/embeddings/LiteLLMEmbeddingEngine.py#L47-L66)
- [LiteLLMEmbeddingEngine.py:85-109](file://m_flow/adapters/vector/embeddings/LiteLLMEmbeddingEngine.py#L85-L109)

## 依赖关系分析
- 松耦合设计：通过协议与工厂解耦具体提供商实现，新增提供商只需遵循协议即可无缝接入。
- 外部依赖：LiteLLM（异步嵌入）、Tenacity（重试）、NumPy（向量池化）、aiohttp（HTTP 客户端，Ollama 场景）。
- 内部依赖：共享速率限制模块、配置模块、日志工具。

```mermaid
graph LR
LiteLLM["LiteLLMEmbeddingEngine"] --> Proto["EmbeddingEngine 协议"]
LiteLLM --> Rate["embedding_rate_limiter_context_manager"]
LiteLLM --> Tenacity["tenacity 重试"]
LiteLLM --> Numpy["numpy 向量池化"]
LiteLLM --> Logger["日志工具"]
Factory["get_embedding_engine"] --> LiteLLM
Factory --> Fast["FastembedEmbeddingEngine"]
Factory --> Ollama["OllamaEmbeddingEngine"]
```

**图表来源**
- [LiteLLMEmbeddingEngine.py:15-31](file://m_flow/adapters/vector/embeddings/LiteLLMEmbeddingEngine.py#L15-L31)
- [get_embedding_engine.py:84-99](file://m_flow/adapters/vector/embeddings/get_embedding_engine.py#L84-L99)
- [rate_limiting.py:56-58](file://m_flow/shared/rate_limiting.py#L56-L58)

**章节来源**
- [LiteLLMEmbeddingEngine.py:15-31](file://m_flow/adapters/vector/embeddings/LiteLLMEmbeddingEngine.py#L15-L31)
- [get_embedding_engine.py:84-99](file://m_flow/adapters/vector/embeddings/get_embedding_engine.py#L84-L99)

## 性能考量
- **批次大小优化**：建议根据提供商上下文限制与网络状况调整批次大小，默认 36；对大模型可适当减小以避免溢出。
- **智能分块策略**：批量处理能力增强了智能分块功能，能够自动处理超大文本数组，提升资源利用率。
- **吞吐量提升**：批量处理显著减少了 API 调用次数，提高了整体吞吐量和处理效率。
- **限流策略**：在高并发场景启用嵌入限流，避免触发第三方速率限制或被降级。
- **重试退避**：指数退避+抖动可有效缓解瞬时抖动，建议结合熔断策略使用。
- **向量池化**：对超长文本进行重叠池化可提升召回质量，但会增加计算与内存消耗。
- **本地化替代**：在低延迟与隐私要求高的场景，可考虑 FastEmbed 或 Ollama 本地部署。

**更新** 批量处理能力的增强使得引擎能够更高效地处理大规模嵌入任务，特别是在以下场景中表现突出：
- 大规模文档集合的批量嵌入
- 高并发的嵌入服务请求
- 需要优化成本的生产环境
- 对延迟敏感的应用场景

## 故障排查指南
- **常见错误分类**：
  - 认证错误：检查 API 密钥与提供商是否匹配。
  - 参数错误：检查模型、维度、端点与版本号。
  - 上下文超限：减小批次或启用自动分片；必要时调整最大完成令牌。
  - 批量处理错误：检查批量大小配置和内存限制。
- **排查步骤**：
  - 开启模拟模式验证流程完整性。
  - 查看日志输出定位异常阶段（网络、解析、重试）。
  - 在前端设置页核对配置项与掩码密钥处理。
  - 监控批量处理的内存使用情况。
- **测试参考**：
  - 自定义提供商配置项覆盖测试，验证维度与端点生效。
  - 批量大小配置测试，验证不同批次大小的性能表现。

**章节来源**
- [LiteLLMEmbeddingEngine.py:114-116](file://m_flow/adapters/vector/embeddings/LiteLLMEmbeddingEngine.py#L114-L116)
- [save_embedding_config.py:57-60](file://m_flow/config/settings/save_embedding_config.py#L57-L60)
- [test_embedding_config_custom_provider.py:6-19](file://m_flow/tests/unit/infrastructure/vector/embeddings/test_embedding_config_custom_provider.py#L6-L19)

## 结论
LiteLLM 嵌入引擎通过协议化接口与工厂缓存机制，实现了对多家提供商的统一抽象与灵活路由。其内置的上下文溢出处理、批量分片与池化、速率限制与重试策略，显著提升了稳定性与吞吐表现。配合完善的配置系统与前端可视化界面，用户可在 OpenAI、Azure、Ollama、FastEmbed 等多种方案间快速切换与优化，满足不同场景的成本与性能需求。

**更新** 本次批量处理能力增强进一步提升了引擎的性能表现，通过可配置的批量大小和智能分块功能，显著提高了大数集嵌入生成的资源利用率和吞吐量，为生产环境中的大规模嵌入任务提供了更好的解决方案。

## 附录

### 配置指南（后端）
- **关键配置项**：
  - provider：提供商标识（openai、azure、ollama、fastembed、custom）。
  - model：模型标识符（如 openai/text-embedding-3-large）。
  - dimensions：输出向量维度（如 1536、3072）。
  - endpoint：自定义 API 端点（Azure、DashScope 等）。
  - api_key：提供商 API 密钥（支持掩码占位）。
  - api_version：API 版本（Azure 必填）。
  - max_completion_tokens：单次请求最大令牌数。
  - batch_size：批次大小（未指定时默认 100，原默认值为 36）。
  - huggingface_tokenizer：HF 分词器名称（用于预处理）。
- **默认值与行为**：
  - 未指定批次大小时使用默认值 100（已更新）。
  - 自定义提供商可覆盖端点与模型，以兼容第三方兼容层。
  - 批量处理功能自动启用，无需额外配置。

**章节来源**
- [config.py:16-68](file://m_flow/adapters/vector/embeddings/config.py#L16-L68)
- [get_embedding_engine.py:87-88](file://m_flow/adapters/vector/embeddings/get_embedding_engine.py#L87-L88)
- [LiteLLMEmbeddingEngine.py:56](file://m_flow/adapters/vector/embeddings/LiteLLMEmbeddingEngine.py#L56)

### 配置指南（前端）
- **支持的提供商与默认参数**：
  - OpenAI：默认模型 text-embedding-3-large，维度 3072，需 API Key。
  - Azure OpenAI：默认模型 text-embedding-3-large，维度 3072，需 API Key 与端点。
  - Ollama（本地）：默认模型 nomic-embed-text，维度 768，需端点。
  - FastEmbed（本地）：默认模型 BAAI/bge-small-en-v1.5，维度 384，无需密钥。
- **设置页功能**：
  - 表单校验与变更检测。
  - 保存时可选择是否持久化至 .env。
  - 掩码密钥保护，避免明文泄露。
  - 批量大小配置选项（50-300，默认 100）。

**章节来源**
- [EmbeddingConfigStep.tsx:45-83](file://m_flow-frontend/src/components/setup/ConfigWizard/steps/EmbeddingConfigStep.tsx#L45-L83)
- [EmbeddingSettings.tsx:38-42](file://m_flow-frontend/src/components/settings/EmbeddingSettings.tsx#L38-L42)
- [save_embedding_config.py:57-75](file://m_flow/config/settings/save_embedding_config.py#L57-L75)

### 使用示例（概念性）
- **示例目标**：演示在不同提供商间进行智能路由与成本优化。
- **步骤概要**：
  - 在前端设置页选择提供商与模型，填写必要参数（如 Azure 端点与密钥）。
  - 配置合适的批量大小以优化性能（默认 100，可根据需求调整）。
  - 保存配置并持久化至 .env。
  - 通过工厂方法获取嵌入引擎实例，调用 embed_text 执行批量嵌入。
  - 根据返回向量进行向量检索或知识图谱构建。
- **成本优化建议**：
  - 优先选择与应用同区域的提供商以降低延迟与费用。
  - 对高频查询启用嵌入限流，避免触发第三方配额。
  - 使用适当的批量大小平衡吞吐与稳定性。
  - 利用智能分块功能处理超大文本数组。
  - 监控内存使用情况，避免批量处理导致的内存溢出。

**更新** 批量处理能力的增强使得该示例更加实用，特别是在处理大规模文本集合时能够显著提升性能和降低成本。