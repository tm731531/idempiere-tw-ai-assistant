# Qwen API 配置指南

## 概述

Python AI Service 已從 **Claude Sonnet** 切換到 **Qwen Max**（阿里巴巴通義千問），並保留 **Groq Llama** 作為備用模型。

---

## LLM 架構

```
Primary:  Qwen Max (Alibaba DashScope)
          ↓ (if fails)
Fallback: Groq Llama 70B
          ↓ (if fails)
Fallback: Groq Llama 8B (clarification questions)
```

---

## 配置步驟

### 1. 申請 Qwen API Key

1. 訪問：https://dashscope.aliyun.com/
2. 註冊/登入阿里雲帳號
3. 進入控制台 → API Key 管理
4. 建立新的 API Key
5. 複製 key（格式：`sk-xxxxxxxxxxxxxxxx`）

### 2. 配置 .env 文件

```bash
cd /home/tom/idempiere-tw-ai-assistant/service
cp .env.example .env
```

編輯 `.env`：

```bash
# Mock 模式（測試用，不花錢）
MOCK_LLM=true

# Qwen API Key（必填）
DASHSCOPE_API_KEY=sk-你的 key 在這裡

# Groq API Key（必填，用於 fallback）
GROQ_API_KEY=gsk_你的 key 在這裡

# HMAC secret
HMAC_SECRET=test-secret

# 資料庫配置
DB_HOST=localhost
DB_PORT=5432
DB_NAME=idempiere
DB_USER=ai_readonly
DB_PASSWORD=your-password
```

### 3. 安裝依賴

```bash
cd /home/tom/idempiere-tw-ai-assistant/service
pip install -r requirements.txt
```

需要的套件：
- `dashscope>=1.14`（Qwen）
- `langchain-groq>=0.2`（Groq Llama）
- ~~`langchain-anthropic`~~（已移除）

---

## 測試

### 測試 1：Mock 模式（不花錢）

```bash
# .env 中設置 MOCK_LLM=true
cd /home/tom/idempiere-tw-ai-assistant/service
./venv/bin/python -m app.main

# 另一個終端
./venv/bin/python test_manual.py
```

預期結果：
- ✅ `/health` 返回 `{"status": "ok"}`
- ✅ HMAC 驗證正確
- ✅ 返回 mock 回應："Mock response - LLM call skipped in mock mode"

### 測試 2：真實模式（需要 API key）

```bash
# .env 中設置 MOCK_LLM=false
# 填寫真實的 DASHSCOPE_API_KEY 和 GROQ_API_KEY

cd /home/tom/idempiere-tw-ai-assistant/service
./venv/bin/python -m app.main

# 另一個終端
./venv/bin/python test_manual.py
```

預期結果：
- ✅ 返回真實 Qwen 回應
- ✅ `model_used: "qwen_max"`
- ✅ 顯示 token 使用量

---

## 成本說明

### Qwen Max 定價（參考）

| 項目 | 價格 |
|------|------|
| Input | ¥0.04 / 1K tokens |
| Output | ¥0.12 / 1K tokens |

### Groq Llama 定價

| 項目 | 價格 |
|------|------|
| Llama 70B | Free tier available |
| Llama 8B | Free |

### 節省成本建議

1. **開發時使用 Mock 模式**
   ```bash
   MOCK_LLM=true
   ```

2. **生產環境監控 token 使用量**
   - 每次 API 呼叫都會返回 `tokens_used`
   - 記錄到 `AI_ChatLog` 表

3. **使用 fallback 鏈**
   - Qwen Max 失敗時自動切換到 Groq
   - 提高可靠性

---

## 模型切換

如果需要改回 Claude（不建議）：

1. 編輯 `service/app/llm/caller.py`
2. 取消註解 Claude 相關代碼
3. 註解 Qwen 相關代碼
4. 編輯 `service/requirements.txt`
5. 安裝 `langchain-anthropic`
6. 更新 `.env` 中的 `ANTHROPIC_API_KEY`

**但建議使用 Qwen**，因為：
- ✅ 已在專案中完整整合
- ✅ 所有測試通過（39/39）
- ✅ 成本效益更好
- ✅ 亞洲地區延遲更低

---

## 故障排除

### 問題 1: `ModuleNotFoundError: No module named 'dashscope'`

解決：
```bash
pip install -r requirements.txt
```

### 問題 2: `Invalid API Key`

解決：
1. 檢查 `.env` 中的 `DASHSCOPE_API_KEY` 是否正確
2. 確認沒有多餘的空格
3. 確認 API key 已啟用

### 問題 3: `MOCK_LLM=false 但仍然返回 mock 回應`

解決：
1. 檢查 `.env` 是否正確載入
2. 重啟 Python 服務
3. 檢查環境變數：`echo $MOCK_LLM`

### 問題 4: Qwen API 超時

解決：
1. 檢查網路連線
2. 增加 timeout（預設 25 秒）
3. 檢查 DashScope 服務狀態

---

## 參考文檔

- [Qwen DashScope API 文檔](https://help.aliyun.com/zh/dashscope/)
- [Qwen 模型介紹](https://help.aliyun.com/zh/dashscope/developer-reference/model-introduction)
- [Groq Cloud API](https://console.groq.com/docs)

---

**最後更新:** 2026-04-01  
**版本:** Python AI Service v1.0.0 (Qwen Edition)
