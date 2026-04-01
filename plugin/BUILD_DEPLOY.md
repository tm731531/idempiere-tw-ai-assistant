# Build and Deployment Instructions

## Task 14: Build + Deploy + End-to-End Test

## Prerequisites

1. **iDempiere 12** running at `/home/tom/idempiere/`
2. **Python AI Service** running on `localhost:8900`
3. **Maven** installed

## Build Steps

### 1. Build Plugin JAR

```bash
cd /home/tom/idempiere-tw-ai-assistant/plugin
mvn clean package -DskipTests
```

Output: `target/tw.idempiere.ai.assistant-1.0.0-SNAPSHOT.jar`

### 2. Deploy to iDempiere

```bash
# Copy JAR to plugins directory
cp target/tw.idempiere.ai.assistant-1.0.0-SNAPSHOT.jar \
   /opt/idempiere-server/x86_64/plugins/

# Copy 2Pack (after generating it via Pack Out)
cp resources/META-INF/2Pack_1.0.0.zip \
   /opt/idempiere-server/x86_64/plugins/
```

### 3. Configure iDempiere Startup

Add to iDempiere startup parameters (idempiere.properties or command line):

```properties
-DAI_SERVICE_URL=http://localhost:8900
-DAI_HMAC_SECRET=test-secret
```

**Important:** `AI_HMAC_SECRET` must match Python service's `HMAC_SECRET` in `.env`.

### 4. Restart iDempiere

```bash
# Stop iDempiere
/opt/idempiere-server/idempiere-server.sh stop

# Start iDempiere
/opt/idempiere-server/idempiere-server.sh start
```

Or refresh OSGi bundles via telnet:

```bash
telnet localhost 2612
# Password: admin
refresh *
```

### 5. Verify Deployment

Check bundle is active:

```sql
SELECT Name, SymbolicName, Version, Active 
FROM AD_Package 
WHERE Name LIKE '%AI Assistant%';
```

Check form is registered:

```sql
SELECT AD_Form_ID, Name, ClassName 
FROM AD_Form 
WHERE ClassName = 'idempiere.ai.assistant.form.AIChatForm';
```

### 6. Test End-to-End

1. Login to iDempiere Web UI
2. Navigate to: **Tools → AI Assistant** (or wherever you placed the menu)
3. Form should open with chat UI
4. Type a question: "上個月營收最高的客戶是誰？"
5. Click **發送**
6. Wait for AI response (may take 5-30 seconds)
7. Verify answer appears in chat panel
8. Verify audit log saved:

```sql
SELECT Question, Answer, ModelUsed, TokensUsed, ResponseTimeMS 
FROM AI_ChatLog 
ORDER BY Created DESC 
LIMIT 1;
```

## Mock Mode Testing

For testing without LLM API costs:

1. **Python Service** (set in `.env`):
   ```bash
   MOCK_LLM=true
   ```

2. **Test**:
   ```bash
   cd /home/tom/idempiere-tw-ai-assistant/service
   ./venv/bin/python -m app.main
   ```

3. **iDempiere Plugin** will work normally, but Python returns mock responses

## Troubleshooting

### Form doesn't open

Check AD_Form_Access:

```sql
SELECT fa.AD_Role_ID, fa.IsReadWrite 
FROM AD_Form_Access fa
JOIN AD_Form f ON f.AD_Form_ID = fa.AD_Form_ID
WHERE f.ClassName = 'idempiere.ai.assistant.form.AIChatForm';
```

If no rows, run the INSERT from `AIAssistantActivator.afterPackIn()`.

### HMAC authentication fails

Verify secrets match:

**Python (.env):**
```bash
HMAC_SECRET=test-secret
```

**iDempiere (startup):**
```bash
-DAI_HMAC_SECRET=test-secret
```

### Python service not reachable

Test from iDempiere server:

```bash
curl http://localhost:8900/health
# Should return: {"status": "ok", "db": "connected"}
```

### Thread pool issues

Verify plugin uses isolated pool:

```java
// In AIChatForm.java - should be:
private static final ExecutorService AI_THREAD_POOL = Executors.newFixedThreadPool(4);

// NOT:
// Adempiere.getThreadPoolExecutor()  // WRONG!
```

## File Checklist

Before deployment, verify:

```
□ plugin/pom.xml
□ plugin/META-INF/MANIFEST.MF
□ plugin/src/.../AIAssistantActivator.java
□ plugin/src/.../model/MAIChatLog.java
□ plugin/src/.../model/AIAssistantModelFactory.java
□ plugin/src/.../service/AIChatService.java
□ plugin/src/.../service/HmacUtil.java
□ plugin/src/.../form/AIChatForm.java
□ plugin/src/.../form/AIChatFormFactory.java
□ plugin/OSGI-INF/AIAssistantModelFactory.xml
□ plugin/OSGI-INF/AIChatFormFactory.xml
□ plugin/resources/META-INF/2Pack_1.0.0.zip (generated via Pack Out)
```

## Success Criteria

- [ ] Plugin JAR builds successfully
- [ ] 2Pack installs without errors
- [ ] AI Chat form opens from menu
- [ ] Question can be typed and sent
- [ ] AI response appears in chat panel
- [ ] Audit log saved to AI_ChatLog table
- [ ] No errors in iDempiere log
- [ ] No errors in Python service log

---

**Next Steps after Phase 1:**

1. Phase 2: Add more pre-defined queries
2. Phase 2: Add conversation history
3. Phase 2: Add write operations (via iDempiere API)
4. Phase 3: Add prompt injection detection
5. Phase 3: Add cost monitoring
6. Phase 3: Docker containerization
