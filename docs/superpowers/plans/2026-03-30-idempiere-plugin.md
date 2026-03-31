# iDempiere Plugin — Implementation Plan (Phase 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an iDempiere OSGi plugin that provides a ZK Form-based chat UI for the AI assistant, calling the Python service via HMAC-authenticated HTTP, and logging all Q&A to an audit table.

**Architecture:** ZK Form → background thread → HTTP POST to Python → parse response → save audit log → push answer to UI via ServerPush.

**Tech Stack:** Java 17, OSGi, ZK 9.x, java.net.http.HttpClient, com.google.gson, 2Pack, iDempiere PO framework

**Prerequisites:** Python AI Service (Tasks 1-7) must be running on localhost:8900.

**Design Spec:** `docs/superpowers/specs/2026-03-30-idempiere-ai-assistant-design.md` (Rev 5)

**End-to-End Flow:** `docs/superpowers/plans/2026-03-30-end-to-end-overview.md`

**Reference Plugin:** `/home/tom/idempiere-tw-invoice-system/` (follow same patterns)

---

## Project Structure

```
idempiere-tw-ai-assistant/
├── plugin/
│   ├── pom.xml
│   ├── META-INF/
│   │   └── MANIFEST.MF
│   ├── OSGI-INF/
│   │   ├── AIAssistantModelFactory.xml
│   │   └── AIChatFormFactory.xml
│   ├── resources/
│   │   └── META-INF/
│   │       └── 2Pack_1.0.0.zip           # PackOut.xml inside (Incremental2PackActivator naming convention)
│   └── src/idempiere/ai/assistant/
│       ├── AIAssistantActivator.java      # Incremental2PackActivator
│       ├── model/
│       │   ├── MAIChatLog.java            # PO model (@Model)
│       │   └── AIAssistantModelFactory.java
│       ├── service/
│       │   ├── AIChatService.java         # HTTP client + HMAC + Gson
│       │   └── HmacUtil.java              # HMAC-SHA256 helper
│       └── form/
│           ├── AIChatForm.java            # ZK Form UI
│           └── AIChatFormFactory.java      # IFormFactory DS component
├── service/                               # Python (already implemented)
└── ...
```

---

### Task 8: Plugin Scaffold (pom.xml, MANIFEST.MF, Activator)

**Files:**
- Create: `plugin/pom.xml`
- Create: `plugin/META-INF/MANIFEST.MF`
- Create: `plugin/src/idempiere/ai/assistant/AIAssistantActivator.java`

- [ ] **Step 1: Create pom.xml**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>org.idempiere</groupId>
        <artifactId>org.idempiere.parent</artifactId>
        <version>12.0.0-SNAPSHOT</version>
        <relativePath>/home/tom/idempiere/org.idempiere.parent</relativePath>
    </parent>

    <groupId>tw.idempiere</groupId>
    <artifactId>tw.idempiere.ai.assistant</artifactId>
    <version>1.0.0-SNAPSHOT</version>
    <packaging>jar</packaging>

    <dependencies>
        <dependency>
            <groupId>org.idempiere</groupId>
            <artifactId>org.adempiere.base</artifactId>
            <version>${idempiere.version}</version>
            <scope>provided</scope>
        </dependency>
        <dependency>
            <groupId>org.idempiere</groupId>
            <artifactId>org.adempiere.ui.zk</artifactId>
            <version>${idempiere.version}</version>
            <scope>provided</scope>
        </dependency>
        <dependency>
            <groupId>org.osgi</groupId>
            <artifactId>org.osgi.core</artifactId>
            <scope>provided</scope>
        </dependency>
        <dependency>
            <groupId>org.osgi</groupId>
            <artifactId>org.osgi.service.component.annotations</artifactId>
            <scope>provided</scope>
        </dependency>
    </dependencies>
</project>
```

- [ ] **Step 2: Create MANIFEST.MF**

```
Manifest-Version: 1.0
Bundle-ManifestVersion: 2
Bundle-Name: iDempiere TW AI Assistant
Bundle-SymbolicName: tw.idempiere.ai.assistant
Bundle-Version: 1.0.0.qualifier
Bundle-Activator: idempiere.ai.assistant.AIAssistantActivator
Bundle-RequiredExecutionEnvironment: JavaSE-17
Bundle-ActivationPolicy: lazy
Import-Package: com.google.gson,
 javax.crypto,
 javax.crypto.spec,
 org.adempiere.base,
 org.adempiere.exceptions,
 org.adempiere.pipo2,
 org.adempiere.plugin.utils,
 org.adempiere.webui,
 org.adempiere.webui.adwindow,
 org.adempiere.webui.component,
 org.adempiere.webui.factory,
 org.adempiere.webui.panel,
 org.adempiere.webui.session,
 org.adempiere.webui.util,
 org.compiere.model,
 org.compiere.util,
 org.osgi.framework,
 org.osgi.service.component.annotations,
 org.zkoss.zhtml,
 org.zkoss.zk.ui,
 org.zkoss.zk.ui.event,
 org.zkoss.zk.ui.util,
 org.zkoss.zul
Service-Component: OSGI-INF/*.xml
```

- [ ] **Step 3: Create Activator**

```java
// plugin/src/idempiere/ai/assistant/AIAssistantActivator.java
package idempiere.ai.assistant;

import org.adempiere.pipo2.Incremental2PackActivator;

public class AIAssistantActivator extends Incremental2PackActivator {

    @Override
    protected void afterPackIn() {
        // Grant all active roles access to the AI Chat form.
        // Without this, no role can open the form after install.
        String sql = "INSERT INTO AD_Form_Access (AD_Form_Access_UU, AD_Client_ID, AD_Org_ID, "
            + "AD_Role_ID, AD_Form_ID, IsActive, Created, CreatedBy, Updated, UpdatedBy, IsReadWrite) "
            + "SELECT generate_uuid(), r.AD_Client_ID, 0, r.AD_Role_ID, f.AD_Form_ID, 'Y', "
            + "now(), 0, now(), 0, 'Y' "
            + "FROM AD_Role r, AD_Form f "
            + "WHERE f.ClassName = 'idempiere.ai.assistant.form.AIChatForm' "
            + "AND r.IsActive = 'Y' "
            + "AND NOT EXISTS (SELECT 1 FROM AD_Form_Access fa "
            + "  WHERE fa.AD_Role_ID = r.AD_Role_ID AND fa.AD_Form_ID = f.AD_Form_ID)";
        int count = DB.executeUpdate(sql, null);
        if (count > 0) {
            log.info("Granted AI Chat form access to " + count + " roles");
        }
    }
}
```

- [ ] **Step 4: Create directory structure**

```bash
mkdir -p /home/tom/idempiere-tw-ai-assistant/plugin/{META-INF,OSGI-INF,resources/META-INF}
mkdir -p /home/tom/idempiere-tw-ai-assistant/plugin/src/idempiere/ai/assistant/{model,service,form}
```

- [ ] **Step 5: Commit**

```bash
git add plugin/
git commit -m "feat: plugin scaffold — pom.xml, MANIFEST.MF, Activator"
```

---

### Task 9: 2Pack — AI_ChatLog Table + Window + Form + Menu

**Files:**
- Create: `plugin/resources/META-INF/2Pack_1.0.0.zip` (contains PackOut.xml)

This task creates the iDempiere Application Dictionary entries via 2Pack XML. The 2Pack is loaded automatically by `Incremental2PackActivator` on first bundle start.

- [ ] **Step 1: Create PackOut.xml defining AI_ChatLog table**

The 2Pack XML defines:

**Table: AI_ChatLog**
| Column | AD Type | Reference | Mandatory | Key |
|--------|---------|-----------|-----------|-----|
| AI_ChatLog_ID | ID | — | Y | PK |
| AI_ChatLog_UU | String(36) | UUID | Y | — |
| AD_Client_ID | TableDir | — | Y | — |
| AD_Org_ID | TableDir | — | Y | — |
| AD_User_ID | TableDir | AD_User | Y | — |
| AD_Role_ID | TableDir | AD_Role | Y | — |
| SessionID | String(36) | — | N | — |
| Question | Text | — | Y | — |
| Answer | Text | — | N | — |
| ModelUsed | String(40) | — | N | — |
| TokensUsed | Integer | — | N | — |
| QueryUsed | String(100) | — | N | — |
| ResponseTimeMS | Integer | — | N | — |
| Created | DateTime | — | Y | — |
| CreatedBy | Table | AD_User | Y | — |
| Updated | DateTime | — | Y | — |
| UpdatedBy | Table | AD_User | Y | — |
| IsActive | YesNo | — | Y | — |

**Window: AI Chat Log (for admin viewing)**
- Tab: AI_ChatLog (single tab, read-only for viewing)
- Hidden fields (SeqNo=0): AI_ChatLog_ID, AI_ChatLog_UU, Created, CreatedBy, Updated, UpdatedBy
- Displayed fields: AD_Client_ID (ReadOnly), AD_Org_ID, IsActive, AD_User_ID, AD_Role_ID, SessionID, Question, Answer, ModelUsed, TokensUsed, QueryUsed, ResponseTimeMS

**Form: AI Chat (AD_Form entry)**
- Name: "AI Chat"
- ClassName: `idempiere.ai.assistant.form.AIChatForm`
- Description: "AI-powered Q&A assistant for ERP data"

**Menu entry:**
- Name: "AI Assistant"
- Action: Form
- AD_Form: AI Chat

**Note:** The actual PackOut.xml is generated by iDempiere's Pack Out process or written manually. The structure follows the same pattern as `/home/tom/idempiere-tw-invoice-system/resources/META-INF/`. Since 2Pack XML is verbose (~500 lines), the implementing agent should use iDempiere's Pack Out tool to generate it after manually creating the table/window/form via the Application Dictionary, then export.

- [ ] **Step 2: Alternative approach — create via SQL + export**

If using the Application Dictionary UI:
1. Login to iDempiere as System Admin
2. Create Table `AI_ChatLog` with all columns listed above
3. Create Window `AI Chat Log` with one Tab
4. Create Form `AI Chat` pointing to the Java class
5. Create Menu entry
6. Use Pack Out to export to `resources/META-INF/2Pack_1.0.0.zip`

- [ ] **Step 3: Verify 2Pack structure matches tw-invoice reference**

```bash
# Reference: tw-invoice 2Pack structure
ls /home/tom/idempiere-tw-invoice-system/resources/META-INF/
# Should contain a directory with PackOut.xml inside
```

- [ ] **Step 4: 2Pack Quality Checklist (lessons from tw-invoice)**

Before committing, verify the PackOut.xml against these known pitfalls:

```
□ ZIP internal structure: {name}/dict/PackOut.xml (verify with unzip -l)
□ AI_ChatLog_UU column: IsUpdateable=Y (NOT N, or UUID will always be NULL)
□ All AD_Field elements have <SeqNoGrid> matching <SeqNo> (Grid View crashes without this)
□ All AD_Field elements have <IsDisplayedGrid>Y</IsDisplayedGrid>
□ Standard field UUIDs are stable placeholders (not randomly generated)
□ AD_Form ClassName = "idempiere.ai.assistant.form.AIChatForm" (exact match)
□ Menu entry has correct AD_Menu parent (e.g., under Utilities)
□ No stale files in OSGI-INF/ (only AIAssistantModelFactory.xml + AIChatFormFactory.xml)
```

Post-install DB verification:
```sql
-- Verify table exists
SELECT count(*) FROM information_schema.tables WHERE table_schema='adempiere' AND table_name='ai_chatlog';
-- Verify form registered
SELECT AD_Form_ID, Name, ClassName FROM AD_Form WHERE ClassName LIKE '%AIChatForm%';
-- Verify menu entry
SELECT Name, Action FROM AD_Menu WHERE Name = 'AI Assistant';
-- Verify _UU column is updateable
SELECT ColumnName, IsUpdateable FROM AD_Column WHERE AD_Table_ID = (SELECT AD_Table_ID FROM AD_Table WHERE TableName='AI_ChatLog') AND ColumnName='AI_ChatLog_UU';
```

- [ ] **Step 5: Commit**

```bash
git add plugin/resources/
git commit -m "feat: 2Pack — AI_ChatLog table, window, form, menu entries"
```

---

### Task 10: MAIChatLog PO Model + ModelFactory

**Files:**
- Create: `plugin/src/idempiere/ai/assistant/model/MAIChatLog.java`
- Create: `plugin/src/idempiere/ai/assistant/model/AIAssistantModelFactory.java`
- Create: `plugin/OSGI-INF/AIAssistantModelFactory.xml`

- [ ] **Step 1: Create MAIChatLog PO model**

```java
// plugin/src/idempiere/ai/assistant/model/MAIChatLog.java
package idempiere.ai.assistant.model;

import java.sql.ResultSet;
import java.util.Properties;
import org.compiere.model.MTable;
import org.compiere.model.PO;

@org.adempiere.base.Model(table = "AI_ChatLog")
public class MAIChatLog extends PO {

    public static final String Table_Name = "AI_ChatLog";

    // Column name constants
    public static final String COLUMNNAME_AI_ChatLog_ID = "AI_ChatLog_ID";
    public static final String COLUMNNAME_AI_ChatLog_UU = "AI_ChatLog_UU";
    public static final String COLUMNNAME_Question = "Question";
    public static final String COLUMNNAME_Answer = "Answer";
    public static final String COLUMNNAME_ModelUsed = "ModelUsed";
    public static final String COLUMNNAME_TokensUsed = "TokensUsed";
    public static final String COLUMNNAME_QueryUsed = "QueryUsed";
    public static final String COLUMNNAME_ResponseTimeMS = "ResponseTimeMS";
    public static final String COLUMNNAME_SessionID = "SessionID";

    public MAIChatLog(Properties ctx, int AI_ChatLog_ID, String trxName) {
        super(ctx, AI_ChatLog_ID, trxName);
    }

    public MAIChatLog(Properties ctx, ResultSet rs, String trxName) {
        super(ctx, rs, trxName);
    }

    @Override
    protected int get_AccessLevel() {
        return ACCESSLEVEL_CLIENTORG; // 3 = Client+Org
    }

    @Override
    protected POInfo initPO(Properties ctx) {
        int tableId = MTable.getTable_ID(Table_Name);
        if (tableId <= 0) return null; // Guard: 2Pack may not have run yet
        return POInfo.getPOInfo(ctx, tableId, get_TrxName());
    }

    // --- Getters and Setters ---

    public void setQuestion(String question) {
        set_Value(COLUMNNAME_Question, question);
    }

    public String getQuestion() {
        return (String) get_Value(COLUMNNAME_Question);
    }

    public void setAnswer(String answer) {
        set_Value(COLUMNNAME_Answer, answer);
    }

    public String getAnswer() {
        return (String) get_Value(COLUMNNAME_Answer);
    }

    public void setModelUsed(String model) {
        set_Value(COLUMNNAME_ModelUsed, model);
    }

    public void setTokensUsed(int tokens) {
        set_Value(COLUMNNAME_TokensUsed, tokens);
    }

    public void setQueryUsed(String query) {
        set_Value(COLUMNNAME_QueryUsed, query);
    }

    public void setResponseTimeMS(int ms) {
        set_Value(COLUMNNAME_ResponseTimeMS, ms);
    }

    public void setSessionID(String sessionId) {
        set_Value(COLUMNNAME_SessionID, sessionId);
    }

    public void setAD_User_ID(int id) {
        set_Value("AD_User_ID", id);
    }

    public void setAD_Role_ID(int id) {
        set_Value("AD_Role_ID", id);
    }
}
```

- [ ] **Step 2: Create ModelFactory**

```java
// plugin/src/idempiere/ai/assistant/model/AIAssistantModelFactory.java
package idempiere.ai.assistant.model;

import org.adempiere.base.AnnotationBasedModelFactory;
import org.osgi.service.component.annotations.Component;
import org.compiere.model.IModelFactory;

@Component(immediate = true, service = IModelFactory.class)
public class AIAssistantModelFactory extends AnnotationBasedModelFactory {
    // Scans this package for @Model annotations (finds MAIChatLog)
}
```

- [ ] **Step 3: Create OSGi DS component XML**

```xml
<!-- plugin/OSGI-INF/AIAssistantModelFactory.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<scr:component xmlns:scr="http://www.osgi.org/xmlns/scr/v1.1.0"
    name="idempiere.ai.assistant.model.AIAssistantModelFactory"
    immediate="true">
    <implementation class="idempiere.ai.assistant.model.AIAssistantModelFactory"/>
    <service>
        <provide interface="org.compiere.model.IModelFactory"/>
    </service>
</scr:component>
```

- [ ] **Step 4: Commit**

```bash
git add plugin/src/idempiere/ai/assistant/model/ plugin/OSGI-INF/AIAssistantModelFactory.xml
git commit -m "feat: MAIChatLog PO model + AIAssistantModelFactory"
```

---

### Task 11: AIChatService (HTTP Client + HMAC + Gson + Error Mapping)

**Files:**
- Create: `plugin/src/idempiere/ai/assistant/service/HmacUtil.java`
- Create: `plugin/src/idempiere/ai/assistant/service/AIChatService.java`

- [ ] **Step 1: Create HMAC utility**

```java
// plugin/src/idempiere/ai/assistant/service/HmacUtil.java
package idempiere.ai.assistant.service;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.util.HexFormat;

public class HmacUtil {

    /**
     * Compute HMAC-SHA256 of the given body string.
     * The body MUST be the exact bytes that will be sent as the HTTP request body.
     */
    public static String computeHmac(String body, String secret) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            SecretKeySpec key = new SecretKeySpec(
                secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256");
            mac.init(key);
            byte[] hash = mac.doFinal(body.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(hash);
        } catch (Exception e) {
            throw new RuntimeException("HMAC computation failed", e);
        }
    }
}
```

- [ ] **Step 2: Create AIChatService**

```java
// plugin/src/idempiere/ai/assistant/service/AIChatService.java
package idempiere.ai.assistant.service;

import java.net.ConnectException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.http.HttpTimeoutException;
import java.nio.charset.StandardCharsets;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Properties;
import java.util.logging.Level;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import org.compiere.model.MRole;
import org.compiere.util.CLogger;
import org.compiere.util.DB;
import org.compiere.util.Env;

import idempiere.ai.assistant.model.MAIChatLog;

public class AIChatService {

    private static final CLogger log = CLogger.getCLogger(AIChatService.class);
    private static final Gson gson = new Gson();

    // Singleton HttpClient — reuses connections
    private static final HttpClient HTTP_CLIENT = HttpClient.newBuilder()
        .connectTimeout(Duration.ofSeconds(5))
        .build();

    private final String serviceUrl;
    private final String hmacSecret;

    public AIChatService() {
        this.serviceUrl = System.getProperty("AI_SERVICE_URL", "http://localhost:8900");
        this.hmacSecret = System.getProperty("AI_HMAC_SECRET", "");
        if (hmacSecret.isEmpty()) {
            log.severe("AI_HMAC_SECRET system property not set! AI service will refuse requests.");
        }
    }

    private void validateConfig() throws AIChatException {
        if (hmacSecret.isEmpty()) {
            throw new AIChatException("AI 服務尚未設定，請聯繫管理員設定 AI_HMAC_SECRET");
        }
    }

    /**
     * Ask the AI service a question. Returns the answer string.
     * Throws AIChatException with user-friendly message on error.
     */
    public AIChatResponse ask(String question, Properties ctx) throws AIChatException {
        validateConfig(); // Refuse if HMAC secret not configured
        int adUserId = Env.getAD_User_ID(ctx);
        int adRoleId = Env.getAD_Role_ID(ctx);
        int adClientId = Env.getAD_Client_ID(ctx);
        List<Integer> orgIds = getAccessibleOrgIds(adRoleId, adClientId);

        // Build JSON body
        JsonObject body = new JsonObject();
        body.addProperty("question", question);
        body.addProperty("user_id", adUserId);
        body.addProperty("role_id", adRoleId);
        body.addProperty("client_id", adClientId);
        body.add("org_ids", gson.toJsonTree(orgIds));
        body.addProperty("language", Env.getAD_Language(ctx)); // e.g. "zh_TW"

        String jsonBody = gson.toJson(body);

        // Compute HMAC on the exact bytes we'll send
        String signature = HmacUtil.computeHmac(jsonBody, hmacSecret);

        // Call Python service
        String responseBody = callService(jsonBody, signature);

        // Parse response
        JsonObject resp = JsonParser.parseString(responseBody).getAsJsonObject();
        String answer = resp.get("answer").getAsString();
        String modelUsed = resp.get("model_used").getAsString();
        int tokensUsed = resp.get("tokens_used").getAsInt();
        String queryUsed = resp.has("query_used") && !resp.get("query_used").isJsonNull()
            ? resp.get("query_used").getAsString() : null;
        int elapsedMs = resp.get("elapsed_ms").getAsInt();

        // Save audit log (best-effort)
        try {
            MAIChatLog chatLog = new MAIChatLog(ctx, 0, null);
            chatLog.setAD_User_ID(adUserId);
            chatLog.setAD_Role_ID(adRoleId);
            chatLog.setQuestion(question);
            chatLog.setAnswer(answer);
            chatLog.setModelUsed(modelUsed);
            chatLog.setTokensUsed(tokensUsed);
            chatLog.setQueryUsed(queryUsed);
            chatLog.setResponseTimeMS(elapsedMs);
            if (!chatLog.save()) {
                log.severe("Failed to save AI chat log");
            }
        } catch (Exception e) {
            log.log(Level.SEVERE, "AI chat log save error", e);
            // Don't throw — always return the answer
        }

        return new AIChatResponse(answer, modelUsed, tokensUsed, queryUsed, elapsedMs);
    }

    private String callService(String jsonBody, String signature) throws AIChatException {
        try {
            HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(serviceUrl + "/v1/ask"))
                .timeout(Duration.ofSeconds(30))
                .header("Content-Type", "application/json")
                .header("X-HMAC-Signature", signature)
                .POST(HttpRequest.BodyPublishers.ofString(jsonBody, StandardCharsets.UTF_8))
                .build();

            HttpResponse<String> response = HTTP_CLIENT.send(request,
                HttpResponse.BodyHandlers.ofString());

            switch (response.statusCode()) {
                case 200:
                    return response.body();
                case 401:
                    log.severe("HMAC authentication failed — check AI_HMAC_SECRET");
                    throw new AIChatException("系統設定錯誤，請聯繫管理員");
                case 429:
                    throw new AIChatException("請求過於頻繁，請稍候再試");
                case 500:
                    log.severe("Python service error: " + response.body());
                    throw new AIChatException("AI 服務暫時無法使用");
                default:
                    log.severe("Unexpected status " + response.statusCode());
                    throw new AIChatException("AI 服務發生錯誤");
            }
        } catch (HttpTimeoutException e) {
            throw new AIChatException("請求逾時，請縮短問題再試");
        } catch (ConnectException e) {
            throw new AIChatException("AI 服務未啟動，請聯繫管理員");
        } catch (AIChatException e) {
            throw e; // re-throw our own exceptions
        } catch (Exception e) {
            log.log(Level.SEVERE, "HTTP call failed", e);
            throw new AIChatException("AI 服務無法連線");
        }
    }

    /**
     * Get list of org IDs accessible by this role.
     * Handles IsAccessAllOrgs=Y (SuperUser) by returning all client orgs.
     */
    private List<Integer> getAccessibleOrgIds(int adRoleId, int adClientId) {
        // Check if role has access to all orgs
        MRole role = MRole.get(Env.getCtx(), adRoleId);
        if (role.isAccessAllOrgs()) {
            // SuperUser or role with IsAccessAllOrgs=Y: return all orgs for this client
            List<Integer> allOrgs = new ArrayList<>();
            allOrgs.add(0); // * org
            String sql = "SELECT AD_Org_ID FROM AD_Org WHERE AD_Client_ID=? AND IsActive='Y' AND AD_Org_ID > 0";
            try (PreparedStatement pstmt = DB.prepareStatement(sql, null)) {
                pstmt.setInt(1, adClientId);
                ResultSet rs = pstmt.executeQuery();
                while (rs.next()) {
                    allOrgs.add(rs.getInt(1));
                }
            } catch (Exception e) {
                log.log(Level.SEVERE, "Failed to get all orgs", e);
            }
            return allOrgs;
        }

        // Normal role: query AD_Role_OrgAccess (MRole.getOrgAccess is private)
        List<Integer> orgIds = new ArrayList<>();
        String sql = "SELECT AD_Org_ID FROM AD_Role_OrgAccess "
                   + "WHERE AD_Role_ID=? AND AD_Client_ID=? AND IsActive='Y'";
        try (PreparedStatement pstmt = DB.prepareStatement(sql, null)) {
            pstmt.setInt(1, adRoleId);
            pstmt.setInt(2, adClientId);
            ResultSet rs = pstmt.executeQuery();
            while (rs.next()) {
                orgIds.add(rs.getInt(1));
            }
        } catch (Exception e) {
            log.log(Level.SEVERE, "Failed to get org access", e);
        }
        if (!orgIds.contains(0)) {
            orgIds.add(0, 0); // Always include * org
        }
        return orgIds;
    }

    // --- Response DTO ---
    public static class AIChatResponse {
        public final String answer;
        public final String modelUsed;
        public final int tokensUsed;
        public final String queryUsed;
        public final int elapsedMs;

        public AIChatResponse(String answer, String modelUsed, int tokensUsed,
                              String queryUsed, int elapsedMs) {
            this.answer = answer;
            this.modelUsed = modelUsed;
            this.tokensUsed = tokensUsed;
            this.queryUsed = queryUsed;
            this.elapsedMs = elapsedMs;
        }
    }

    // --- Exception ---
    public static class AIChatException extends Exception {
        public AIChatException(String userMessage) {
            super(userMessage);
        }
    }
}
```

- [ ] **Step 3: Commit**

```bash
git add plugin/src/idempiere/ai/assistant/service/
git commit -m "feat: AIChatService — HTTP client, HMAC signing, Gson, error mapping, audit log"
```

---

### Task 12: AIChatForm (ZK UI + Background Thread + ServerPush)

**Files:**
- Create: `plugin/src/idempiere/ai/assistant/form/AIChatForm.java`

- [ ] **Step 1: Create the ZK Form**

```java
// plugin/src/idempiere/ai/assistant/form/AIChatForm.java
package idempiere.ai.assistant.form;

import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import org.adempiere.webui.panel.ADForm;
import org.adempiere.webui.util.ServerPushTemplate;
import org.adempiere.webui.util.ZkContextRunnable;
import org.compiere.util.CLogger;
import org.compiere.util.Env;
import org.zkoss.zk.ui.Desktop;
import org.zkoss.zk.ui.event.Event;
import org.zkoss.zk.ui.event.Events;
import org.zkoss.zk.ui.util.DesktopCleanup;
import org.zkoss.zul.Borderlayout;
import org.zkoss.zul.Button;
import org.zkoss.zul.Center;
import org.zkoss.zul.Div;
import org.zkoss.zul.Html;
import org.zkoss.zul.South;
import org.zkoss.zul.Hbox;
import org.zkoss.zul.Textbox;
import org.zkoss.zul.Vlayout;

import idempiere.ai.assistant.service.AIChatService;
import idempiere.ai.assistant.service.AIChatService.AIChatException;
import idempiere.ai.assistant.service.AIChatService.AIChatResponse;

// NO @Form annotation — we use explicit IFormFactory (Task 13) instead.
// Using both @Form + IFormFactory causes double registration.
public class AIChatForm extends ADForm {

    private static final CLogger log = CLogger.getCLogger(AIChatForm.class);
    private static final long serialVersionUID = 1L;

    // ISOLATED thread pool — do NOT use Adempiere.getThreadPoolExecutor()
    // That is shared with all iDempiere background tasks. AI requests (up to 30s)
    // would starve scheduled processes, async document processing, etc.
    // Max 4 concurrent AI requests system-wide.
    private static final ExecutorService AI_THREAD_POOL = Executors.newFixedThreadPool(4);

    private Div chatPanel;
    private Textbox inputBox;
    private Button btnSend;
    private Button btnClear;

    private final AIChatService aiService = new AIChatService();
    private volatile boolean formClosed = false;

    @Override
    protected void initForm() {
        Borderlayout layout = new Borderlayout();
        layout.setWidth("100%");
        layout.setHeight("100%");
        appendChild(layout);

        // Chat panel (scrollable)
        Center center = new Center();
        center.setAutoscroll(true);
        layout.appendChild(center);

        chatPanel = new Div();
        chatPanel.setStyle("padding: 10px; overflow-y: auto;");
        center.appendChild(chatPanel);

        // Input area (bottom)
        South south = new South();
        south.setHeight("60px");
        south.setStyle("padding: 5px;");
        layout.appendChild(south);

        Hbox inputArea = new Hbox();
        inputArea.setWidth("100%");
        inputArea.setAlign("center");
        south.appendChild(inputArea);

        inputBox = new Textbox();
        inputBox.setHflex("1");
        inputBox.setPlaceholder("Ask a question about your ERP data...");
        inputArea.appendChild(inputBox);

        btnSend = new Button("Send");
        btnSend.setStyle("margin-left: 5px;");
        inputArea.appendChild(btnSend);

        btnClear = new Button("Clear");
        btnClear.setStyle("margin-left: 5px;");
        inputArea.appendChild(btnClear);

        // Event listeners
        btnSend.addEventListener(Events.ON_CLICK, this::onSend);
        inputBox.addEventListener(Events.ON_OK, this::onSend); // Enter key
        btnClear.addEventListener(Events.ON_CLICK, e -> {
            chatPanel.getChildren().clear();
        });

        // Desktop cleanup listener — guard against form closed while waiting
        getDesktop().addListener((DesktopCleanup) d -> this.formClosed = true);

        // Welcome message
        appendMessage("ai", "Hello! Ask me anything about your ERP data.");
    }

    private void onSend(Event event) {
        String question = inputBox.getValue();
        if (question == null || question.isBlank()) return;

        // 1. Disable UI (we ARE in the ZK event thread)
        btnSend.setDisabled(true);
        inputBox.setDisabled(true);
        inputBox.setValue("");

        // 2. Show user message + loading indicator
        appendMessage("user", question);
        appendMessage("ai", "AI 思考中...");

        // 3. Enable server push (REQUIRED for pushing from background thread)
        Desktop desktop = getDesktop();
        desktop.enableServerPush(true);

        // 4. Capture context for background thread
        final String q = question;

        // 5. Run HTTP call in ISOLATED thread pool (NOT iDempiere's shared pool)
        AI_THREAD_POOL.submit(new ZkContextRunnable() {
            @Override
            protected void doRun() {
                if (formClosed) return;

                try {
                    AIChatResponse response = aiService.ask(q, Env.getCtx());

                    // 6. Push result to UI thread
                    ServerPushTemplate template = new ServerPushTemplate(desktop);
                    template.executeAsync(() -> {
                        if (formClosed) return;
                        replaceLastMessage("ai", response.answer);
                        btnSend.setDisabled(false);
                        inputBox.setDisabled(false);
                        inputBox.focus();
                    });
                } catch (AIChatException e) {
                    ServerPushTemplate template = new ServerPushTemplate(desktop);
                    template.executeAsync(() -> {
                        if (formClosed) return;
                        replaceLastMessage("ai", e.getMessage());
                        btnSend.setDisabled(false);
                        inputBox.setDisabled(false);
                    });
                } catch (Exception e) {
                    log.log(java.util.logging.Level.SEVERE, "AI chat error", e);
                    ServerPushTemplate template = new ServerPushTemplate(desktop);
                    template.executeAsync(() -> {
                        if (formClosed) return;
                        replaceLastMessage("ai", "An unexpected error occurred.");
                        btnSend.setDisabled(false);
                        inputBox.setDisabled(false);
                    });
                }
            }
        });
    }

    private void appendMessage(String sender, String text) {
        String bgColor = "user".equals(sender) ? "#DCF8C6" : "#F1F0F0";
        String align = "user".equals(sender) ? "right" : "left";
        String label = "user".equals(sender) ? "You" : "AI";

        Html bubble = new Html(String.format(
            "<div style='text-align:%s; margin:5px 0;'>"
            + "<div style='display:inline-block; max-width:80%%; padding:8px 12px; "
            + "border-radius:12px; background:%s; text-align:left;'>"
            + "<b>%s:</b> %s</div></div>",
            align, bgColor, label, escapeHtml(text)
        ));
        chatPanel.appendChild(bubble);
    }

    private void replaceLastMessage(String sender, String text) {
        // Remove the last child (loading message) and add the real answer
        int count = chatPanel.getChildren().size();
        if (count > 0) {
            chatPanel.getChildren().remove(count - 1);
        }
        appendMessage(sender, text);
    }

    private String escapeHtml(String text) {
        if (text == null) return "";
        return text.replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;")
                   .replace("\"", "&quot;")
                   .replace("\n", "<br/>");
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add plugin/src/idempiere/ai/assistant/form/AIChatForm.java
git commit -m "feat: AIChatForm — ZK chat UI with background thread and ServerPush"
```

---

### Task 13: AIChatFormFactory (OSGi DS Registration)

**Files:**
- Create: `plugin/src/idempiere/ai/assistant/form/AIChatFormFactory.java`
- Create: `plugin/OSGI-INF/AIChatFormFactory.xml`

- [ ] **Step 1: Create FormFactory**

```java
// plugin/src/idempiere/ai/assistant/form/AIChatFormFactory.java
package idempiere.ai.assistant.form;

import org.adempiere.webui.factory.IFormFactory;
import org.adempiere.webui.panel.ADForm;
import org.osgi.service.component.annotations.Component;

@Component(immediate = true, service = IFormFactory.class)
public class AIChatFormFactory implements IFormFactory {

    @Override
    public ADForm newFormInstance(String formName) {
        if ("idempiere.ai.assistant.form.AIChatForm".equals(formName)) {
            return new AIChatForm();
        }
        return null;
    }
}
```

- [ ] **Step 2: Create OSGi DS component XML**

```xml
<!-- plugin/OSGI-INF/AIChatFormFactory.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<scr:component xmlns:scr="http://www.osgi.org/xmlns/scr/v1.1.0"
    name="idempiere.ai.assistant.form.AIChatFormFactory"
    immediate="true">
    <implementation class="idempiere.ai.assistant.form.AIChatFormFactory"/>
    <service>
        <provide interface="org.adempiere.webui.factory.IFormFactory"/>
    </service>
</scr:component>
```

- [ ] **Step 3: Commit**

```bash
git add plugin/src/idempiere/ai/assistant/form/AIChatFormFactory.java plugin/OSGI-INF/AIChatFormFactory.xml
git commit -m "feat: AIChatFormFactory — OSGi DS registration for ZK form"
```

---

### Task 14: Build JAR + Deploy + End-to-End Test

**Files:**
- Modify: `plugin/pom.xml` (if needed)

- [ ] **Step 1: Build the plugin JAR**

```bash
cd /home/tom/idempiere-tw-ai-assistant/plugin
mvn clean package -DskipTests
# Output: target/tw.idempiere.ai.assistant-1.0.0-SNAPSHOT.jar
```

- [ ] **Step 2: Deploy to iDempiere**

```bash
# Copy JAR to plugins directory
cp target/tw.idempiere.ai.assistant-*.jar /opt/idempiere-server/x86_64/plugins/

# Restart iDempiere or refresh OSGi bundles
# Option A: Full restart
# sudo systemctl restart idempiere

# Option B: OSGi console refresh (if Gogo shell available)
# telnet localhost 12612
# install file:/opt/idempiere-server/x86_64/plugins/tw.idempiere.ai.assistant-1.0.0-SNAPSHOT.jar
# start <bundle_id>
```

- [ ] **Step 3: Verify 2Pack installed**

```sql
-- Check table exists
SELECT count(*) FROM information_schema.tables
WHERE table_schema = 'adempiere' AND table_name = 'ai_chatlog';

-- Check form registered
SELECT Name, ClassName FROM AD_Form WHERE ClassName LIKE '%AIChatForm%';

-- Check menu entry
SELECT Name FROM AD_Menu WHERE Name = 'AI Assistant';
```

- [ ] **Step 4: Set HMAC secret**

Add to iDempiere startup:
```bash
# In /opt/idempiere-server/x86_64/idempiere.sh or idempiere.ini
-DAI_HMAC_SECRET=your-shared-secret-here
-DAI_SERVICE_URL=http://localhost:8900
```

Ensure the same secret is in `service/.env`:
```
HMAC_SECRET=your-shared-secret-here
```

- [ ] **Step 5: Ensure Python service is running**

```bash
cd /home/tom/idempiere-tw-ai-assistant/service
python -m app.main &
curl http://localhost:8900/health
# → {"status": "ok", "db": "connected"}
```

- [ ] **Step 6: End-to-end test**

1. Login to iDempiere Web UI
2. Navigate to menu: AI Assistant
3. Form should open with welcome message
4. Type: "今年每月營收多少？"
5. Click Send
6. Verify: button disables, "AI 思考中..." appears
7. Wait 3-5 seconds
8. Verify: answer appears with revenue data
9. Check audit log: open Window "AI Chat Log"
10. Verify: Q&A entry exists with model, tokens, response time

- [ ] **Step 7: Test error scenarios**

1. Stop Python service → type question → should see "AI 服務未啟動"
2. Set wrong HMAC secret → should see "系統設定錯誤"
3. Send 21 questions in 1 minute → should see "請求過於頻繁"

- [ ] **Step 8: Commit final state**

```bash
git add -A
git commit -m "feat: plugin build + deploy + end-to-end verification complete"
git push
```

---

## Spec Coverage Check (Plugin)

| Spec Requirement | Task |
|-----------------|------|
| ZK Form via IFormFactory | Task 12, 13 |
| Isolated thread pool (NOT shared getThreadPoolExecutor) | Task 12 |
| ServerPushTemplate.executeAsync | Task 12 |
| desktop.enableServerPush(true) | Task 12 |
| DesktopCleanup guard | Task 12 |
| Double-click guard (button disabled) | Task 12 |
| java.net.http.HttpClient singleton | Task 11 |
| HMAC-SHA256 on raw body bytes | Task 11 |
| Gson for JSON | Task 11 |
| Error mapping (401/429/500/timeout/refused) | Task 11 |
| MAIChatLog PO with @Model | Task 10 |
| AI_ChatLog_UU, Updated, UpdatedBy columns | Task 9 |
| AnnotationBasedModelFactory | Task 10 |
| IFormFactory DS component | Task 13 |
| Incremental2PackActivator | Task 8 |
| 2Pack: table + window + form + menu | Task 9 |
| Best-effort audit log (trxName=null, try-catch) | Task 11 |
| Get org_ids from AD_Role_OrgAccess | Task 11 |
| No SvrProcess / No IProcessFactory | Task 8 (not created) |
| HMAC secret from system property | Task 11, 14 |
| Empty HMAC secret refused (validateConfig) | Task 11 |
| SuperUser IsAccessAllOrgs handled | Task 11 |
| afterPackIn grants AD_Form_Access | Task 8 |
| @Model import: org.adempiere.base.Model | Task 10 |
| initPO tableId <= 0 guard | Task 10 |
| AI_ChatLog_UU IsUpdateable=Y | Task 9 (checklist) |
| SeqNoGrid / IsDisplayedGrid for Grid View | Task 9 (checklist) |
| org.adempiere.plugin.utils in Import-Package | Task 8 |

---

## Lessons from tw-invoice (must-read before implementation)

These pitfalls were discovered during tw-invoice-system development. Every one applies to this plugin:

### Deployment SOP
```bash
# 1. Build
cd plugin/ && mvn clean package -DskipTests

# 2. Kill any dual JVM instances
ps aux | grep java | grep idempiere | wc -l  # should be 1 or 0

# 3. Copy JAR
cp target/tw.idempiere.ai.assistant-*.jar /opt/idempiere-server/x86_64/plugins/

# 4. Restart iDempiere (wait 30s if port in TIME_WAIT)
sudo systemctl restart idempiere
sleep 30

# 5. Verify bundle started
# OSGi console: telnet localhost 12612 → ss tw.idempiere.ai

# 6. Verify 2Pack installed
psql -U adempiere idempiere -c "SELECT count(*) FROM ad_package_imp WHERE Name LIKE '%AI%'"

# 7. Login, test AI Chat form
```

### Development Iteration (re-install / re-deploy)
```bash
# If 2Pack needs to re-run (e.g., changed PackOut.xml):
# 1. Delete 2Pack install records
psql -U adempiere idempiere -c "
DELETE FROM ad_package_imp_detail WHERE ad_package_imp_id IN (SELECT ad_package_imp_id FROM ad_package_imp WHERE Name LIKE '%AI%');
DELETE FROM ad_package_imp WHERE Name LIKE '%AI%';
"
# 2. Bump version in ZIP filename (2Pack_1.0.0.zip → 2Pack_1.0.1.zip)
# 3. Rebuild + redeploy + restart

# If only Java code changed (no 2Pack changes):
# Just rebuild JAR + copy to plugins/ + restart (or OSGi update)
```

### Version Bump Strategy
- Change ZIP filename: `2Pack_1.0.0.zip` → `2Pack_1.0.1.zip`
- Update `PackOut.xml Version=` attribute to match
- Keep existing AD_Field UUIDs stable across versions
- Only add new elements, don't modify existing UUIDs
