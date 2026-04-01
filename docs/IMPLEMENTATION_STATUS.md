# iDempiere TW AI Assistant - 實現狀態追蹤

**最後更新:** 2026-04-01 09:30 (UTC+8)
**當前階段:** Phase 1 - Python AI Service ✅ COMPLETED
**整體進度:** 7/14 任務完成 (50%)

---

## 📊 任務總覽

| 任務 | 名稱 | 狀態 | 完成時間 | 負責人 |
|------|------|------|----------|--------|
| **Task 1** | Project Scaffold + Config | ✅ COMPLETED | 2026-04-01 08:35 | Qwen Code |
| **Task 2** | PII Masking Layer | ✅ COMPLETED | 2026-04-01 08:45 | Qwen Code |
| **Task 3** | Query Registry + Executor | ✅ COMPLETED | 2026-04-01 08:55 | Qwen Code |
| **Task 4** | LLM Caller + Fallback | ✅ COMPLETED | 2026-04-01 09:05 | Qwen Code |
| **Task 5** | Router Pipeline | ✅ COMPLETED | 2026-04-01 09:15 | Qwen Code |
| **Task 6** | FastAPI Endpoint + HMAC + Rate Limit | ✅ COMPLETED | 2026-04-01 09:25 | Qwen Code |
| **Task 7** | DB Setup + Manual Test | ✅ COMPLETED | 2026-04-01 09:30 | Qwen Code |
| **Task 8** | Plugin Scaffold | ⏳ PENDING | - | - |
| **Task 9** | 2Pack - AI_ChatLog Table + Window + Form + Menu | ⏳ PENDING | - | - |
| **Task 10** | MAIChatLog PO Model + ModelFactory | ⏳ PENDING | - | - |
| **Task 11** | AIChatService (HTTP + HMAC + Gson) | ⏳ PENDING | - | - |
| **Task 12** | AIChatForm (ZK UI) | ⏳ PENDING | - | - |
| **Task 13** | AIChatFormFactory (OSGi Registration) | ⏳ PENDING | - | - |
| **Task 14** | Build + Deploy + End-to-End Test | ⏳ PENDING | - | - |

---

## 📝 詳細進度記錄

### Task 1: Project Scaffold + Config
**狀態:** ✅ COMPLETED  
**完成時間:** 2026-04-01 08:35  
**負責人:** Qwen Code  
**計劃文件:** `docs/superpowers/plans/2026-03-30-python-ai-service.md` (Task 1 章節)  
**Git Commit:** `d73173d`

#### 完成清單
- [x] `service/requirements.txt` - FastAPI, langchain, psycopg2, pytest 等
- [x] `service/.env.example` - 環境變數範本（MOCK_LLM=true 預設）
- [x] `service/app/__init__.py` - 模組初始化
- [x] `service/app/config.py` - 環境變數載入（支持 MOCK_LLM 模式）
- [x] `service/tests/__init__.py` - 測試模組初始化
- [x] `service/tests/conftest.py` - pytest fixtures（設置測試環境變數）
- [x] `.gitignore` - Git 忽略規則

#### 實作筆記
```
- 建立 Python 虛擬環境：service/venv/
- 安裝所有依賴成功（pip install -r requirements.txt）
- 驗證導入：fastapi, psycopg2, langchain_anthropic, langchain_groq 全部成功
- conftest.py 在測試前設置環境變數，避免 config.py 崩潰
- MOCK_LLM 預設為 true，開發測試不需 API key
```

#### 測試驗證
- [x] `pip install -r requirements.txt` 成功
- [x] `python -c "import fastapi, psycopg2; print('OK')"` 通過
- [x] Git commit 完成

#### 下一步
繼續 Task 2: PII Masking Layer

---

### Task 2: PII Masking Layer
**狀態:** ✅ COMPLETED  
**完成時間:** 2026-04-01 08:45  
**負責人:** Qwen Code  
**計劃文件:** `docs/superpowers/plans/2026-03-30-python-ai-service.md` (Task 2 章節)  
**Git Commit:** `33c32fd`

#### 完成清單
- [x] `service/app/masking/__init__.py`
- [x] `service/app/masking/rules.py` - PII 欄位規則（name, taxid, phone, email, address, birthday）
- [x] `service/app/masking/masker.py` - PIIMasker 類別（mask/unmask/sanitize_input）
- [x] `service/tests/test_masking.py` - 10 個測試

#### 實作筆記
```
- Token 格式：[PII_PREFIX_NNN]，例如 [PII_C_001] 代表 name
- 使用 contextvars 實現 request-scoped 的 PII mapping
- sanitize_input() 移除用戶輸入中的 PII token 模式，防止 prompt injection
- 10 個測試全部通過
```

#### 測試驗證
- [x] 10 個 masking 測試全部通過

---

### Task 3: Query Registry + Executor
**狀態:** ✅ COMPLETED  
**完成時間:** 2026-04-01 08:55  
**負責人:** Qwen Code  
**計劃文件:** `docs/superpowers/plans/2026-03-30-python-ai-service.md` (Task 3 章節)  
**Git Commit:** `e8ef32b`

#### 完成清單
- [x] `service/app/queries/__init__.py`
- [x] `service/app/queries/registry.py` - get_query/list_queries/get_query_descriptions
- [x] `service/app/queries/executor.py` - QueryExecutor + ThreadedConnectionPool
- [x] `service/app/queries/definitions/__init__.py`
- [x] `service/app/queries/definitions/sales.py` - 3 個預定義查詢
- [x] `service/tests/test_registry.py` - 6 個測試
- [x] `service/tests/test_executor.py` - 6 個測試

#### 實作筆記
```
- 3 個預定義查詢：top_customers_by_revenue, order_status_by_documentno, monthly_revenue_summary
- 所有查詢都包含 AD_Org_ID = ANY(%(org_ids)s) 過濾器
- 使用 psycopg2.pool.ThreadedConnectionPool（線程安全）
- fetchmany(200) 作為安全網，防止返回無邊界結果
- 12 個測試全部通過
```

#### 測試驗證
- [x] 6 個 registry 測試通過
- [x] 6 個 executor 測試通過

---

### Task 4: LLM Caller with Fallback + Token Usage
**狀態:** ✅ COMPLETED  
**完成時間:** 2026-04-01 09:05  
**負責人:** Qwen Code  
**計劃文件:** `docs/superpowers/plans/2026-03-30-python-ai-service.md` (Task 4 章節)  
**Git Commit:** `0510474`

#### 完成清單
- [x] `service/app/llm/__init__.py`
- [x] `service/app/llm/prompts.py` - 系統提示詞
- [x] `service/app/llm/caller.py` - LLMCaller 類別
- [x] `service/tests/test_caller.py` - 3 個測試

#### 實作筆記
```
- 支持 3 個模型：sonnet (primary), llama_70b (fallback), llama_8b (clarification)
- Fallback 鏈：sonnet → llama_70b
- 所有 LLM 呼叫使用 asyncio.to_thread() 避免阻塞 event loop
- timeout=25s（小於 Java 的 30s，防止 orphaned requests）
- MOCK_LLM=true 時返回 mock 回應（不花錢）
- 3 個測試通過
```

#### 測試驗證
- [x] 3 個 caller 測試通過

---

### Task 5: Router Pipeline
**狀態:** ✅ COMPLETED  
**完成時間:** 2026-04-01 09:15  
**負責人:** Qwen Code  
**計劃文件:** `docs/superpowers/plans/2026-03-30-python-ai-service.md` (Task 5 章節)  
**Git Commit:** `3e007bd`

#### 完成清單
- [x] `service/app/router.py` - process_question 主流程
- [x] `service/tests/test_router.py` - 7 個測試

#### 實作筆記
```
- 流程：sanitize → classify/select → execute → mask → LLM → unmask
- 使用單個 Sonnet 呼叫同時分類和選擇查詢
- 強制注入 ad_client_id/org_ids 從 request context（不從 LLM 輸出）
- 支持 3 種分類：database_query, general_knowledge, clarification
- 7 個測試全部通過
```

#### 測試驗證
- [x] 7 個 router 測試通過

---

### Task 6: FastAPI Endpoint + HMAC + Rate Limit
**狀態:** ✅ COMPLETED  
**完成時間:** 2026-04-01 09:25  
**負責人:** Qwen Code  
**計劃文件:** `docs/superpowers/plans/2026-03-30-python-ai-service.md` (Task 6 章節)  
**Git Commit:** `aca4999`

#### 完成清單
- [x] `service/app/main.py` - FastAPI 應用
- [x] `service/tests/test_integration.py` - 7 個測試

#### 實作筆記
```
- POST /v1/ask: HMAC-SHA256 驗證（針對原始 body bytes）
- GET /health: 健康檢查
- Rate limit: 20 requests/user/minute
- 錯誤處理：永遠不將 exception 細節或 PII 回傳給用戶
- 使用 lifespan context manager 初始化 DB pool
- 7 個 integration 測試通過
```

#### 測試驗證
- [x] 7 個 integration 測試通過
- [x] /health endpoint 返回正確
- [x] /v1/ask endpoint HMAC 驗證通過

---

### Task 7: DB Setup + Manual Test
**狀態:** ✅ COMPLETED  
**完成時間:** 2026-04-01 09:30  
**負責人:** Qwen Code  
**計劃文件:** `docs/superpowers/plans/2026-03-30-python-ai-service.md` (Task 7 章節)  
**Git Commit:** `6dc784f`

#### 完成清單
- [x] `scripts/create_readonly_user.sql` - PostgreSQL read-only user 腳本
- [x] `service/test_manual.py` - 手動測試腳本

#### 實作筆記
```
- create_readonly_user.sql: 建立 ai_readonly 用戶，只讀權限，statement_timeout=10s
- test_manual.py: 測試 /health, /v1/ask, HMAC 驗證
- 服務啟動：cd service/ && ./venv/bin/python -m app.main
```

#### 測試驗證
- [x] 39 個 pytest 測試全部通過

---

### Task 8-14: iDempiere Plugin
**狀態:** ⏳ PENDING (等待 Python Service 完成)

---

## 🔧 環境設定

### Python 版本
- 目標：Python 3.11+
- 目前：`python --version` → (待確認)

### iDempiere 版本
- 目標：iDempiere 12 (release-12)
- 路徑：`/home/tom/idempiere/`

### 參考系統
- tw-invoice: `/home/tom/idempiere-tw-invoice-system/`

### 資料庫
- PostgreSQL: localhost:5432
- Database: `idempiere`
- Schema: `adempiere`

---

## 📋 檢查清單 (每任務完成後勾選)

### 通用檢查清單
- [ ] 所有測試通過 (`pytest tests/ -v`)
- [ ] 程式碼符合設計規範
- [ ] Git commit 完成（英文訊息）
- [ ] 狀態文件已更新
- [ ] 下一個任務的上下文已準備

### Python Service 專屬檢查
- [ ] TDD 流程：先寫測試 → 失敗 → 實現 → 通過
- [ ] 無動態 SQL（所有 SQL 在 `queries/definitions/`）
- [ ] PII 遮蔽使用 `[PII_*]` 格式
- [ ] HMAC 驗證原始 bytes
- [ ] 錯誤訊息不包含 PII 或 stack trace
- [ ] `ad_client_id`/`org_ids` 從 request 注入

### Plugin 專屬檢查
- [ ] 使用 `AI_THREAD_POOL`（非 `getThreadPoolExecutor()`）
- [ ] HMAC 簽署原始 JSON bytes
- [ ] `org_ids` 從 `AD_Role_OrgAccess` 查詢
- [ ] 錯誤訊息映射為中文
- [ ] 審計日誌 best-effort 保存

---

## 🚨 已知問題與風險

| 問題 | 影響 | 解決方案 | 狀態 |
|------|------|----------|------|
| 無 | - | - | ✅ 無 |

---

## 📚 參考文件

| 文件 | 路徑 |
|------|------|
| 設計規範 | `docs/superpowers/specs/2026-03-30-idempiere-ai-assistant-design.md` |
| Python 計劃 | `docs/superpowers/plans/2026-03-30-python-ai-service.md` |
| Plugin 計劃 | `docs/superpowers/plans/2026-03-30-idempiere-plugin.md` |
| 端到端流程 | `docs/superpowers/plans/2026-03-30-end-to-end-overview.md` |
| 代理配置 | `AGENTS.md` |
| Domain Brain | `CLAUDE.md` |

---

## 🔄 交接說明

### 如果中斷，接手者請：

1. **閱讀此文件** → 了解當前進度
2. **查看 Git 歷史** → 了解已完成的工作
   ```bash
   git log --oneline -10
   git status
   ```
3. **檢查測試狀態** → 確認一切正常
   ```bash
   cd service/
   pytest tests/ -v
   ```
4. **繼續下一個任務** → 按照計劃文件實現

### 給未來自己的提醒

- **TDD 嚴格要求**: 先寫測試 → 驗證失敗 → 實現 → 驗證通過
- **不要跳過 conftest.py**: 很多測試依賴它
- **HMAC 驗證**: 簽名/驗證都是針對原始 bytes，不是 canonical JSON
- **org_ids 一定是 list**: psycopg2 對 list 和 tuple 的適應不同
- **錯誤處理**: 永遠不要將異常細節回傳給用戶

---

## 📊 進度時間線

```
2026-04-01 08:23  專案啟動，開始實現 Task 1
2026-04-01 08:35  Task 1 完成（Project Scaffold + Config）✅
2026-04-01 08:45  Task 2 完成（PII Masking Layer）✅
2026-04-01 08:55  Task 3 完成（Query Registry + Executor）✅
2026-04-01 09:05  Task 4 完成（LLM Caller + Fallback）✅
2026-04-01 09:15  Task 5 完成（Router Pipeline）✅
2026-04-01 09:25  Task 6 完成（FastAPI Endpoint + HMAC + Rate Limit）✅
2026-04-01 09:30  Task 7 完成（DB Setup + Manual Test）✅
2026-04-01 09:35  Python Service 完整測試通過（39/39）✅
2026-04-01 ??:??  Task 8 完成（預計）
...
```

---

## ✨ 完成標準 (Phase 1 Done Criteria)

- [ ] 所有 pytest 通過 (37 測試)
- [ ] `/health` 返回 `{"status": "ok", "db": "connected"}`
- [ ] 一次成功的 `/v1/ask` 端到端測試（真實 LLM + 真實 DB）
- [ ] Plugin 部署成功，AI Chat form 可開啟
- [ ] 端到端 Q&A 流程正常運作

---

**最後更新:** 2026-04-01 08:23  
**更新者:** Qwen Code (初始狀態建立)
