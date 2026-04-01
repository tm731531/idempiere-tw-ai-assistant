# iDempiere Plugin Implementation Knowledge Base

**Created:** 2026-04-01 09:50 (UTC+8)  
**Purpose:** Knowledge reference for Tasks 8-14 (iDempiere Plugin implementation)  
**Sources:** tw-invoice reference project, iDempiere source code, design spec (Rev 5)

---

## 1. Project Structure

### Directory Layout
```
plugin/
├── pom.xml
├── META-INF/
│   └── MANIFEST.MF
├── OSGI-INF/
│   ├── AIAssistantModelFactory.xml
│   └── AIChatFormFactory.xml
├── resources/
│   └── META-INF/
│       └── 2Pack_1.0.0.zip          # Contains: {name}/dict/PackOut.xml
└── src/idempiere/ai/assistant/
    ├── AIAssistantActivator.java
    ├── model/
    │   ├── MAIChatLog.java
    │   └── AIAssistantModelFactory.java
    ├── service/
    │   ├── AIChatService.java
    │   └── HmacUtil.java
    └── form/
        ├── AIChatForm.java
        └── AIChatFormFactory.java
```

### pom.xml Key Sections
```xml
<parent>
    <groupId>org.idempiere</groupId>
    <artifactId>org.adempiere.parent</artifactId>
    <version>12.0.0-SNAPSHOT</version>
    <relativePath>/home/tom/idempiere/org.idempiere.parent</relativePath>
</parent>

<properties>
    <idempiere.version>12.0.0-SNAPSHOT</idempiere.version>
</properties>

<dependencies>
    <!-- iDempiere Core -->
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
    
    <!-- OSGi DS Annotations -->
    <dependency>
        <groupId>org.osgi</groupId>
        <artifactId>org.osgi.service.component.annotations</artifactId>
        <scope>provided</scope>
    </dependency>
    
    <!-- System-scoped iDempiere plugins (use absolute paths) -->
    <dependency>
        <groupId>org.adempiere</groupId>
        <artifactId>org.adempiere.pipo</artifactId>
        <version>12.0.0</version>
        <scope>system</scope>
        <systemPath>/opt/idempiere-server/x86_64/plugins/org.adempiere.pipo_12.0.0.*.jar</systemPath>
    </dependency>
</dependencies>

<build>
    <sourceDirectory>src</sourceDirectory>
    <resources>
        <resource>
            <directory>${project.basedir}</directory>
            <includes><include>OSGI-INF/**</include></includes>
        </resource>
    </resources>
    <plugins>
        <plugin>
            <groupId>org.apache.maven.plugins</groupId>
            <artifactId>maven-jar-plugin</artifactId>
            <version>3.3.0</version>
            <configuration>
                <archive>
                    <manifestFile>META-INF/MANIFEST.MF</manifestFile>
                </archive>
            </configuration>
        </plugin>
    </plugins>
</build>
```

### MANIFEST.MF Key Headers
```
Manifest-Version: 1.0
Bundle-ManifestVersion: 2
Bundle-Name: iDempiere TW AI Assistant
Bundle-SymbolicName: tw.idempiere.ai.assistant
Bundle-Version: 1.0.0.qualifier
Bundle-Activator: idempiere.ai.assistant.AIAssistantActivator
Bundle-RequiredExecutionEnvironment: JavaSE-17
Service-Component: OSGI-INF/*.xml
Import-Package: com.google.gson,
 javax.crypto,
 javax.crypto.spec,
 org.adempiere.base,
 org.adempiere.exceptions,
 org.adempiere.pipo2,
 org.adempiere.webui,
 org.adempiere.webui.util,
 org.compiere.model,
 org.compiere.util,
 org.osgi.framework,
 org.osgi.service.component.annotations,
 org.zkoss.zk.ui,
 org.zkoss.zk.ui.event,
 org.zkoss.zul
```

---

## 2. OSGi Bundle Pattern

### Activator Class (Incremental2PackActivator)
```java
package idempiere.ai.assistant;

import org.adempiere.pipo2.Incremental2PackActivator;
import org.compiere.util.DB;
import java.util.logging.Logger;

public class AIAssistantActivator extends Incremental2PackActivator {
    private static final Logger log = Logger.getLogger(AIAssistantActivator.class.getName());

    @Override
    protected void afterPackIn() {
        // Grant all active roles access to the AI Chat form
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

### 2Pack File Naming
- ZIP filename: `2Pack_1.0.0.zip` (version matches bundle version)
- Internal structure: `{bundle_name}/dict/PackOut.xml`
- Example: `tw_idempiere_ai_assistant/dict/PackOut.xml`

### OSGi DS Component XML
```xml
<!-- OSGI-INF/AIAssistantModelFactory.xml -->
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

---

## 3. PO Model Pattern

### MAIChatLog PO Class
```java
package idempiere.ai.assistant.model;

import java.sql.ResultSet;
import java.util.Properties;
import org.adempiere.base.Model;
import org.compiere.model.MTable;
import org.compiere.model.PO;
import org.compiere.model.POInfo;

@Model(table = MAIChatLog.Table_Name)
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

### ModelFactory Pattern
```java
package idempiere.ai.assistant.model;

import org.adempiere.base.AnnotationBasedModelFactory;
import org.adempiere.base.IModelFactory;
import org.osgi.service.component.annotations.Component;

@Component(immediate = true, service = IModelFactory.class)
public class AIAssistantModelFactory extends AnnotationBasedModelFactory {

    @Override
    protected String[] getPackages() {
        return new String[]{"idempiere.ai.assistant.model"};
    }
}
```

---

## 4. Form Factory Pattern

### IFormFactory Implementation
```java
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

### ZK Form UI Pattern
```java
package idempiere.ai.assistant.form;

import org.adempiere.webui.panel.ADForm;
import org.zkoss.zul.*;
import org.zkoss.zk.ui.event.Event;
import org.zkoss.zk.ui.event.EventListener;
import org.zkoss.zk.ui.util.DesktopCleanup;

public class AIChatForm extends ADForm {
    
    private Div chatPanel;
    private Textbox inputBox;
    private Button btnSend;
    private volatile boolean formClosed = false;
    
    @Override
    protected void initForm() {
        // Main layout
        Borderlayout layout = new Borderlayout();
        layout.setWidth("100%");
        layout.setHeight("100%");
        appendChild(layout);
        
        // Center: Chat panel
        Center center = new Center();
        center.setAutoscroll(true);
        layout.appendChild(center);
        
        chatPanel = new Div();
        chatPanel.setStyle("padding: 10px; overflow-y: auto; height: 400px;");
        center.appendChild(chatPanel);
        
        // South: Input area
        South south = new South();
        south.setHeight("60px");
        south.setCollapsible(false);
        layout.appendChild(south);
        
        Hbox inputArea = new Hbox();
        inputArea.setWidth("100%");
        inputArea.setSpacing("5px");
        south.appendChild(inputArea);
        
        inputBox = new Textbox();
        inputBox.setHflex("1");
        inputBox.setPlaceholder("輸入您的問題...");
        inputArea.appendChild(inputBox);
        
        btnSend = new Button("發送");
        btnSend.setStyle("min-width: 80px;");
        inputArea.appendChild(btnSend);
        
        // Event listeners
        btnSend.addEventListener("onClick", new EventListener<Event>() {
            @Override
            public void onEvent(Event event) {
                sendQuestion();
            }
        });
        
        inputBox.addEventListener("onOK", new EventListener<Event>() {
            @Override
            public void onEvent(Event event) {
                sendQuestion();
            }
        });
        
        // Desktop cleanup guard
        getDesktop().addListener((DesktopCleanup) d -> this.formClosed = true);
    }
    
    private void sendQuestion() {
        String question = inputBox.getText().trim();
        if (question.isEmpty()) return;
        
        // Disable UI
        btnSend.setDisabled(true);
        inputBox.setDisabled(true);
        
        // Show loading message
        appendMessage("AI", "AI 思考中...");
        
        // Run in background thread (see Thread Pool Pattern below)
    }
    
    private void appendMessage(String sender, String text) {
        String bgColor = "user".equals(sender) ? "#DCF8C6" : "#F1F0F0";
        String align = "user".equals(sender) ? "right" : "left";
        
        Html bubble = new Html(String.format(
            "<div style='text-align:%s; margin:5px 0;'>"
            + "<div style='display:inline-block; max-width:80%%; padding:8px 12px; "
            + "border-radius:12px; background:%s; text-align:left;'>"
            + "<b>%s:</b> %s</div></div>",
            align, bgColor, sender, escapeHtml(text)
        ));
        chatPanel.appendChild(bubble);
        chatPanel.getParent().scrollTo(0, chatPanel.getParent().getClientHeight());
    }
    
    private String escapeHtml(String text) {
        return text.replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;");
    }
}
```

### ServerPushTemplate Pattern
```java
import org.adempiere.webui.util.ServerPushTemplate;
import org.adempiere.webui.util.ZkContextRunnable;
import org.zkoss.zk.ui.Desktop;

// Enable server push
Desktop desktop = getDesktop();
desktop.enableServerPush(true);

// Run in background thread
AI_THREAD_POOL.submit(new ZkContextRunnable() {
    @Override
    protected void doRun() {
        // Guard against form closed
        if (formClosed) return;
        
        try {
            // Background work here
            AIChatResponse response = aiService.ask(question, Env.getCtx());
            
            // Push result to UI thread
            ServerPushTemplate template = new ServerPushTemplate(desktop);
            template.executeAsync(() -> {
                // UI update here (runs in ZK event thread)
                // Remove loading message
                chatPanel.getChildren().clear();
                appendMessage("AI", response.answer);
                
                // Re-enable UI
                btnSend.setDisabled(false);
                inputBox.setDisabled(false);
                inputBox.setFocus(true);
            });
        } catch (Exception e) {
            // Handle error
        }
    }
});
```

---

## 5. Key iDempiere APIs

### Permission Check (MRole.getFormAccess)
```java
import org.compiere.model.MRole;
import org.compiere.util.Env;

int adRoleId = Env.getAD_Role_ID(ctx);
boolean hasAccess = MRole.getFormAccess(ctx, adRoleId, formId);
if (!hasAccess) {
    Messagebox.show("您沒有權限使用此功能", "錯誤", Messagebox.OK, Messagebox.ERROR);
    return;
}
```

### Org Access Query (AD_Role_OrgAccess)
```java
import org.compiere.util.DB;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.util.ArrayList;
import java.util.List;

private List<Integer> getAccessibleOrgIds(int adRoleId, int adClientId) {
    MRole role = MRole.get(Env.getCtx(), adRoleId);
    if (role.isAccessAllOrgs()) {
        // SuperUser: return all orgs for this client
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
    
    // Normal role: query AD_Role_OrgAccess
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
```

### Context Methods (Env)
```java
import org.compiere.util.Env;

Properties ctx = Env.getCtx();
int adUserId = Env.getAD_User_ID(ctx);
int adRoleId = Env.getAD_Role_ID(ctx);
int adClientId = Env.getAD_Client_ID(ctx);
String language = Env.getAD_Language(ctx); // e.g., "zh_TW"
```

### Database Access (DB.prepareStatement)
```java
import org.compiere.util.DB;
import java.sql.PreparedStatement;
import java.sql.ResultSet;

// Use null for auto-commit (no transaction context)
String sql = "SELECT COUNT(*) FROM AI_ChatLog WHERE AD_User_ID=?";
try (PreparedStatement pstmt = DB.prepareStatement(sql, null)) {
    pstmt.setInt(1, adUserId);
    ResultSet rs = pstmt.executeQuery();
    if (rs.next()) {
        return rs.getInt(1);
    }
}
```

---

## 6. HTTP Client Pattern

### HttpClient Singleton
```java
import java.net.http.HttpClient;
import java.time.Duration;

private static final HttpClient HTTP_CLIENT = HttpClient.newBuilder()
    .connectTimeout(Duration.ofSeconds(5))
    .build();
```

### HMAC-SHA256 Computation
```java
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.util.HexFormat;

public class HmacUtil {

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

### Gson JSON Handling
```java
import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

private static final Gson gson = new Gson();

// Build request
JsonObject body = new JsonObject();
body.addProperty("question", question);
body.addProperty("user_id", adUserId);
body.addProperty("role_id", adRoleId);
body.addProperty("client_id", adClientId);
body.add("org_ids", gson.toJsonTree(orgIds));
body.addProperty("language", language);

String jsonBody = gson.toJson(body);

// Parse response
JsonObject resp = JsonParser.parseString(responseBody).getAsJsonObject();
String answer = resp.get("answer").getAsString();
String modelUsed = resp.get("model_used").getAsString();
int tokensUsed = resp.get("tokens_used").getAsInt();
String queryUsed = resp.has("query_used") && !resp.get("query_used").isJsonNull()
    ? resp.get("query_used").getAsString() : null;
int elapsedMs = resp.get("elapsed_ms").getAsInt();
```

---

## 7. Thread Pool Pattern

### ISOLATED ExecutorService
```java
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

// CRITICAL: Use isolated pool, NOT iDempiere's shared getThreadPoolExecutor()
// AI requests can take up to 30s and would starve scheduled processes
private static final ExecutorService AI_THREAD_POOL = Executors.newFixedThreadPool(4);
```

### ZkContextRunnable Usage
```java
import org.adempiere.webui.util.ZkContextRunnable;

AI_THREAD_POOL.submit(new ZkContextRunnable() {
    @Override
    protected void doRun() {
        // This runs in background thread with ZK context preserved
        // Locale and session context are automatically restored
        
        // Guard against form closed
        if (formClosed) return;
        
        try {
            // Background work here
            AIChatResponse response = aiService.ask(question, Env.getCtx());
            
            // Push to UI thread
            ServerPushTemplate template = new ServerPushTemplate(getDesktop());
            template.executeAsync(() -> {
                updateUI(response);
            });
        } catch (Exception e) {
            log.log(Level.SEVERE, "AI request failed", e);
        }
    }
});
```

---

## 8. Error Mapping

| HTTP Status | Exception | User Message (Chinese) |
|-------------|-----------|------------------------|
| 401 | `AIChatException` | 系統設定錯誤，請聯繫管理員 |
| 429 | `AIChatException` | 請求過於頻繁，請稍候再試 |
| 500 | `AIChatException` | AI 服務暫時無法使用 |
| Timeout | `HttpTimeoutException` | 請求逾時，請縮短問題再試 |
| Connection Refused | `ConnectException` | AI 服務未啟動，請聯繫管理員 |
| Generic | `Exception` | AI 服務無法連線 |

### AIChatService Error Handling
```java
try {
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
```

---

## 9. Configuration

### System Properties (iDempiere startup)
```bash
# Add to iDempiere startup parameters (idempiere.properties or command line)
-DAI_HMAC_SECRET=same-secret-as-python-env
```

### MSysConfig Table
```sql
-- Set AI service URL (optional, default: http://localhost:8900)
INSERT INTO AD_SysConfig (AD_SysConfig_UU, AD_Client_ID, AD_Org_ID, 
    ConfigValue, Description, EntityType, IsActive, Created, CreatedBy, Updated, UpdatedBy)
VALUES (generate_uuid(), 0, 0, 'http://localhost:8900', 
    'AI Service URL', 'U', 'Y', now(), 0, now(), 0);
```

### Java Code Access
```java
String serviceUrl = System.getProperty("AI_SERVICE_URL", "http://localhost:8900");
String hmacSecret = System.getProperty("AI_HMAC_SECRET", "");
```

---

## 10. 2Pack Checklist

Before deploying, verify:

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

### Post-install DB Verification
```sql
-- Verify table exists
SELECT count(*) FROM information_schema.tables 
WHERE table_schema='adempiere' AND table_name='ai_chatlog';

-- Verify form registered
SELECT AD_Form_ID, Name, ClassName FROM AD_Form 
WHERE ClassName LIKE '%AIChatForm%';

-- Verify menu entry
SELECT Name, Action FROM AD_Menu WHERE Name = 'AI Assistant';

-- Verify _UU column is updateable
SELECT ColumnName, IsUpdateable FROM AD_Column 
WHERE AD_Table_ID = (SELECT AD_Table_ID FROM AD_Table WHERE TableName='AI_ChatLog') 
AND ColumnName='AI_ChatLog_UU';
```

---

## 11. Build & Deploy

### Build Command
```bash
cd /home/tom/idempiere-tw-ai-assistant/plugin/
mvn clean package -DskipTests
```

### Deploy Command
```bash
cp target/tw.idempiere.ai.assistant-1.0.0-SNAPSHOT.jar \
   /opt/idempiere-server/x86_64/plugins/
```

### Refresh OSGi Bundles
```bash
# In iDempiere OSGi console (telnet localhost 2612)
refresh *
# Or restart iDempiere server
```

### Verify Deployment
```sql
-- Check bundle is active
SELECT * FROM AD_Package WHERE Name LIKE '%AI Assistant%';

-- Check form is accessible
SELECT f.Name, f.ClassName, fa.AD_Role_ID 
FROM AD_Form f 
LEFT JOIN AD_Form_Access fa ON f.AD_Form_ID = fa.AD_Form_ID 
WHERE f.ClassName = 'idempiere.ai.assistant.form.AIChatForm';
```

---

## 12. References

| Document | Path |
|----------|------|
| Plugin Plan | `docs/superpowers/plans/2026-03-30-idempiere-plugin.md` |
| Design Spec | `docs/superpowers/specs/2026-03-30-idempiere-ai-assistant-design.md` |
| End-to-End Flow | `docs/superpowers/plans/2026-03-30-end-to-end-overview.md` |
| Reference Plugin | `/home/tom/idempiere-tw-invoice-system/` |
| iDempiere Source | `/home/tom/idempiere/` (release-12) |

---

**Last Updated:** 2026-04-01 09:50  
**Prepared by:** Explorer Agent (Haiku)  
**For:** Plugin Dev Agent (Tasks 8-14 implementation)
