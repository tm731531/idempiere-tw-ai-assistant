# iDempiere TW AI Assistant - 實現狀態追蹤

**最後更新:** 2026-04-01 08:23 (UTC+8)
**當前階段:** Phase 1 - Python AI Service
**整體進度:** 0/14 任務完成 (0%)

---

## 📊 任務總覽

| 任務 | 名稱 | 狀態 | 完成時間 | 負責人 |
|------|------|------|----------|--------|
| **Task 1** | Project Scaffold + Config | ⏳ PENDING | - | - |
| **Task 2** | PII Masking Layer | ⏳ PENDING | - | - |
| **Task 3** | Query Registry + Executor | ⏳ PENDING | - | - |
| **Task 4** | LLM Caller + Fallback | ⏳ PENDING | - | - |
| **Task 5** | Router Pipeline | ⏳ PENDING | - | - |
| **Task 6** | FastAPI Endpoint + HMAC + Rate Limit | ⏳ PENDING | - | - |
| **Task 7** | DB Setup + Manual Test | ⏳ PENDING | - | - |
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
**狀態:** ⏳ PENDING  
**計劃文件:** `docs/superpowers/plans/2026-03-30-python-ai-service.md` (Task 1 章節)  
**預計檔案:** 7 個

#### 待辦清單
- [ ] `service/requirements.txt`
- [ ] `service/.env.example`
- [ ] `service/app/__init__.py`
- [ ] `service/app/config.py`
- [ ] `service/tests/__init__.py`
- [ ] `service/tests/conftest.py`
- [ ] `.gitignore` (根目錄)

#### 實作筆記
```
（尚未開始）
```

#### 測試驗證
- [ ] `pip install -r requirements.txt` 成功
- [ ] `python -c "import fastapi, psycopg2; print('OK')"` 通過
- [ ] Git commit 完成

---

### Task 2: PII Masking Layer
**狀態:** ⏳ PENDING  
**計劃文件:** `docs/superpowers/plans/2026-03-30-python-ai-service.md` (Task 2 章節)  
**預計檔案:** 4 個

#### 待辦清單
- [ ] `service/app/masking/__init__.py`
- [ ] `service/app/masking/rules.py`
- [ ] `service/app/masking/masker.py`
- [ ] `service/tests/test_masking.py`

#### 實作筆記
```
（尚未開始）
```

#### 測試驗證
- [ ] 10 個 masking 測試全部通過

---

### Task 3: Query Registry + Executor
**狀態:** ⏳ PENDING  
**計劃文件:** `docs/superpowers/plans/2026-03-30-python-ai-service.md` (Task 3 章節)  
**預計檔案:** 7 個

#### 待辦清單
- [ ] `service/app/queries/__init__.py`
- [ ] `service/app/queries/registry.py`
- [ ] `service/app/queries/executor.py`
- [ ] `service/app/queries/definitions/__init__.py`
- [ ] `service/app/queries/definitions/sales.py`
- [ ] `service/tests/test_registry.py`
- [ ] `service/tests/test_executor.py`

#### 實作筆記
```
（尚未開始）
```

#### 測試驗證
- [ ] 6 個 registry 測試通過
- [ ] 5 個 executor 測試通過

---

### Task 4: LLM Caller with Fallback + Token Usage
**狀態:** ⏳ PENDING  
**計劃文件:** `docs/superpowers/plans/2026-03-30-python-ai-service.md` (Task 4 章節)  
**預計檔案:** 4 個

#### 待辦清單
- [ ] `service/app/llm/__init__.py`
- [ ] `service/app/llm/prompts.py`
- [ ] `service/app/llm/caller.py`
- [ ] `service/tests/test_caller.py`

#### 實作筆記
```
（尚未開始）
```

#### 測試驗證
- [ ] 4 個 caller 測試通過

---

### Task 5: Router Pipeline
**狀態:** ⏳ PENDING  
**計劃文件:** `docs/superpowers/plans/2026-03-30-python-ai-service.md` (Task 5 章節)  
**預計檔案:** 2 個

#### 待辦清單
- [ ] `service/app/router.py`
- [ ] `service/tests/test_router.py`

#### 實作筆記
```
（尚未開始）
```

#### 測試驗證
- [ ] 7 個 router 測試通過

---

### Task 6: FastAPI Endpoint + HMAC + Rate Limit
**狀態:** ⏳ PENDING  
**計劃文件:** `docs/superpowers/plans/2026-03-30-python-ai-service.md` (Task 6 章節)  
**預計檔案:** 2 個

#### 待辦清單
- [ ] `service/app/main.py`
- [ ] `service/tests/test_integration.py`

#### 實作筆記
```
（尚未開始）
```

#### 測試驗證
- [ ] 5 個 integration 測試通過
- [ ] `/health` endpoint 返回正確
- [ ] `/v1/ask` endpoint HMAC 驗證通過

---

### Task 7: DB Setup + Manual Test
**狀態:** ⏳ PENDING  
**計劃文件:** `docs/superpowers/plans/2026-03-30-python-ai-service.md` (Task 7 章節)  
**預計檔案:** 2 個

#### 待辦清單
- [ ] `scripts/create_readonly_user.sql`
- [ ] `service/.env` (從 .env.example 複製並填寫)

#### 實作筆記
```
（尚未開始）
```

#### 測試驗證
- [ ] PostgreSQL read-only user 建立成功
- [ ] Python service 啟動成功
- [ ] 手動測試 `/v1/ask` 成功

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
2026-04-01 ??:??  Task 1 完成 (預計)
2026-04-01 ??:??  Task 2 完成 (預計)
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
