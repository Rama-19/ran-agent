---
name: ragflow-dataset-ingest
description: "用于 RAGFlow 数据集任务：创建、列出、查看、更新或删除数据集；上传、列出、更新或删除文档；启动或停止解析；检查解析状态；通过 `search.py` 检索分块；以及列出已配置的模型。"
metadata:
  openclaw:
    requires:
      env:
        - RAGFLOW_API_URL
        - RAGFLOW_API_KEY
      bins:
        - python3
    primaryEnv: RAGFLOW_API_KEY
---

# RAGFlow 数据集与检索

仅使用 `scripts/` 目录中的内置脚本。
优先使用 `--json` 参数，以便原样转发返回字段。
所有面向用户的输出遵循 `reference.md`。

## 适用场景

- 用户需要创建、列出、查看、更新或删除 RAGFlow 数据集
- 用户需要在数据集中上传、列出、更新或删除文档
- 用户需要启动解析、停止解析或查看解析进度
- 用户需要从一个或多个数据集中检索分块
- 用户需要列出已配置的 RAGFlow 模型

## 核心工作流

1. 首先解析目标数据集或文档的 ID。
2. 从 `scripts/` 中运行对应的脚本。
3. 除非脚本只需要简单文本响应，否则使用 `--json`。
4. 原样返回 API 字段，不要猜测缺失的详情。

常用命令：

```bash
python3 scripts/datasets.py list --json
python3 scripts/datasets.py info DATASET_ID --json
python3 scripts/datasets.py create "示例数据集" --description "季度报告" --json
python3 scripts/update_dataset.py DATASET_ID --name "更新后的数据集" --json
python3 scripts/upload.py DATASET_ID /path/to/file.pdf --json
python3 scripts/upload.py list DATASET_ID --json
python3 scripts/update_document.py DATASET_ID DOC_ID --name "更新后的文档" --json
python3 scripts/parse.py DATASET_ID DOC_ID1 [DOC_ID2 ...] --json
python3 scripts/stop_parse_documents.py DATASET_ID DOC_ID1 [DOC_ID2 ...] --json
python3 scripts/parse_status.py DATASET_ID --json
python3 scripts/search.py "查询内容" --json
python3 scripts/search.py "查询内容" DATASET_ID --json
python3 scripts/search.py --dataset-ids DATASET_ID1,DATASET_ID2 --doc-ids DOC_ID1,DOC_ID2 "查询内容" --json
python3 scripts/search.py --retrieval-test --kb-id DATASET_ID "查询内容" --json
python3 scripts/list_models.py --json
```

## 操作限制

- 任何删除操作前，必须先列出具体条目，并要求用户明确确认后再执行。
- 仅通过明确的数据集 ID 或文档 ID 进行删除。若用户提供名称或模糊描述，须先解析 ID。
- 上传不会自动启动解析，仅在用户明确要求时才启动解析。
- `parse.py` 在发起启动请求后立即返回，使用 `parse_status.py` 查看进度。
- 查询进度时，在最精确的范围内使用 `parse_status.py`：
  - 已指定数据集：检查该数据集
  - 已指定文档 ID：传入 `--doc-ids`
  - 未指定数据集：先列出数据集，再汇总各数据集的状态
- 若解析状态结果中包含 `progress_msg`，直接展示该字段。`FAIL` 状态视为主要错误详情。
- `--retrieval-test` 仅用于单数据集调试，或用户明确要求使用该端点时。

## 输出规范

- 遵循 `reference.md`。
- 3 条及以上条目尽量使用表格展示。
- 原样保留 `api_error`、`error`、`message` 及相关字段。
- 不得捏造进度百分比或推断原因。
