# Plugin Code Review Fixes — 2026-04-01

Reviewed by: Claude Opus (with Domain Brain: idempiere-osgi-bundle + idempiere-2pack + idempiere-po-model)
Code author: Qwen
Status: **14 issues (5 CRITICAL, 4 IMPORTANT, 5 MODERATE)**

**Current state: Plugin cannot deploy successfully.** MANIFEST.MF missing imports → ClassNotFoundException. 2Pack wrong path → dictionary not loaded. ModelFactory XML wrong interface → PO model not discovered.

---

## 🔴 CRITICAL (plugin won't work without these)

### Fix 1: MANIFEST.MF — Missing Import-Package entries

**File:** `plugin/META-INF/MANIFEST.MF`

**Problem:** Several packages used in Java code are not imported in MANIFEST.MF. OSGi will throw `ClassNotFoundException` at runtime.

**Missing packages:**
- `org.adempiere.webui.factory` — used by `AIChatFormFactory.java` (`IFormFactory`)
- `org.adempiere.webui.panel` — used by `AIChatForm.java` (`ADForm`)
- `org.adempiere.webui.util` — used by `AIChatForm.java` (`ServerPushTemplate`, `ZkContextRunnable`)
- `org.compiere.process` — used by `AIAssistantTestProcess.java` (`SvrProcess`, `ProcessInfoParameter`)

**Fix:** Add to Import-Package in MANIFEST.MF:
```
Import-Package: com.google.gson,
 javax.crypto,
 javax.crypto.spec,
 org.adempiere.base,
 org.adempiere.exceptions,
 org.adempiere.model,
 org.adempiere.plugin.utils,
 org.adempiere.pipo2,
 org.adempiere.webui.factory,
 org.adempiere.webui.panel,
 org.adempiere.webui.util,
 org.compiere.model,
 org.compiere.process,
 org.compiere.util,
 org.osgi.framework,
 org.osgi.service.component.annotations,
 org.zkoss.zk.ui,
 org.zkoss.zk.ui.event,
 org.zkoss.zk.ui.util,
 org.zkoss.zul
```

---

### Fix 2: 2Pack ZIP in wrong path

**File:** `plugin/META-INF/2Pack_1.0.0.zip`

**Problem:** `Incremental2PackActivator` searches classpath for `META-INF/2Pack_*.zip`. The pom.xml configures `resources/` as the resource directory. So the ZIP must be at `plugin/resources/META-INF/2Pack_1.0.0.zip`, not `plugin/META-INF/2Pack_1.0.0.zip`.

Current: `plugin/META-INF/2Pack_1.0.0.zip` → NOT on classpath → 2Pack never runs.

**Fix:**
```bash
mkdir -p plugin/resources/META-INF/
mv plugin/META-INF/2Pack_1.0.0.zip plugin/resources/META-INF/2Pack_1.0.0.zip
```

Note: `plugin/META-INF/MANIFEST.MF` stays where it is (that's the correct location for MANIFEST).

---

### Fix 3: afterPackIn missing AD_Form_Access

**File:** `plugin/src/idempiere/ai/assistant/AIAssistantActivator.java`

**Problem:** `afterPackIn()` grants `AD_Process_Access` and `AD_Menu_Access` but NOT `AD_Form_Access`. After install, no role can open the AI Chat form.

**Fix:** Add to `afterPackIn()`:
```java
// Grant form access to all active roles
sql = "INSERT INTO AD_Form_Access (AD_Form_Access_UU, AD_Client_ID, AD_Org_ID, "
    + "AD_Role_ID, AD_Form_ID, IsActive, Created, CreatedBy, Updated, UpdatedBy, IsReadWrite) "
    + "SELECT generate_uuid(), r.AD_Client_ID, 0, r.AD_Role_ID, f.AD_Form_ID, 'Y', "
    + "now(), 0, now(), 0, 'Y' "
    + "FROM AD_Role r, AD_Form f "
    + "WHERE f.ClassName = 'idempiere.ai.assistant.form.AIChatForm' "
    + "AND r.IsActive = 'Y' "
    + "AND NOT EXISTS (SELECT 1 FROM AD_Form_Access fa "
    + "  WHERE fa.AD_Role_ID = r.AD_Role_ID AND fa.AD_Form_ID = f.AD_Form_ID)";
count = DB.executeUpdate(sql, null);
if (count > 0) log.info("Granted AI Chat form access to " + count + " roles");
```

---

### Fix 4: insert_ai_assistant.sql uses hardcoded AD_Process_ID = 54001

**File:** `plugin/insert_ai_assistant.sql`

**Problem:** `AD_Process_ID = 54001` is hardcoded. Any other plugin on the same iDempiere instance that also uses 54001 will cause a primary key conflict.

**Fix:** Use `nextval` or rely entirely on 2Pack (which uses UUID-based resolution). If using manual SQL:
```sql
-- Use sequence instead of hardcoded ID
INSERT INTO AD_Process (AD_Process_ID, ...)
VALUES (nextval('ad_process_sq'), ...);
```

Or better: **remove insert_ai_assistant.sql entirely** and let 2Pack handle all dictionary creation.

---

### Fix 5: PackOut.xml uses hardcoded numeric IDs

**File:** `plugin/resources/META-INF/2Pack_1.0.0.zip` → `PackOut.xml`

**Problem:** All `AD_Process_ID`, `AD_Menu_ID` etc. use `reference="id"` with hardcoded numbers like `54001`. iDempiere 2Pack should use `reference="uuid"` to avoid ID conflicts across environments.

**Fix:** Regenerate PackOut.xml using iDempiere's Pack Out tool, which automatically uses UUID references. Or manually change all references:
```xml
<!-- BEFORE (wrong): -->
<AD_Process_ID reference="id">54001</AD_Process_ID>

<!-- AFTER (correct): -->
<AD_Process_ID reference="uuid">your-generated-uuid-here</AD_Process_ID>
```

---

## 🟡 IMPORTANT (functionality broken)

### Fix 6: OSGI-INF/AIAssistantModelFactory.xml — Wrong interface name

**File:** `plugin/OSGI-INF/AIAssistantModelFactory.xml` line 7

**Problem:** XML declares:
```xml
<provide interface="org.compiere.model.IModelFactory"/>
```
But the actual interface used in Java is:
```java
import org.adempiere.base.IModelFactory;
```

This causes the DS component to register under the wrong interface. iDempiere's model factory lookup won't find it, so `MAIChatLog` falls back to `GenericPO` and `beforeSave()`/`afterSave()` never run.

**Fix:**
```xml
<provide interface="org.adempiere.base.IModelFactory"/>
```

---

### Fix 7: 2Pack missing AD_Form record

**File:** `PackOut.xml`

**Problem:** PackOut.xml defines AD_Process + AD_Menu but NO `AD_Form` record. The AI Chat UI is supposed to be a Form (AIChatForm extends ADForm), but there's no AD_Form entry in the dictionary. The Menu's Action='P' (Process) instead of 'X' (Form).

**Fix:** Add AD_Form definition to PackOut.xml:
```xml
<AD_Form>
    <AD_Form_UU>generate-a-real-uuid</AD_Form_UU>
    <Name>AI Chat</Name>
    <ClassName>idempiere.ai.assistant.form.AIChatForm</ClassName>
    <Description>AI-powered Q&amp;A assistant for ERP data</Description>
    <IsActive>Y</IsActive>
</AD_Form>
```

And change Menu Action from 'P' to 'X', pointing to AD_Form instead of AD_Process.

---

### Fix 8: 2Pack missing AI_ChatLog table definition

**File:** `PackOut.xml`

**Problem:** PackOut.xml does NOT define the `AI_ChatLog` table (no AD_Table, AD_Column entries). `MAIChatLog` PO model depends on this table existing. The audit log will fail on first save because the physical table doesn't exist.

**Fix:** Add full table definition to PackOut.xml:
- AD_Table: AI_ChatLog
- AD_Column: AI_ChatLog_ID, AI_ChatLog_UU, AD_Client_ID, AD_Org_ID, AD_User_ID, AD_Role_ID, SessionID, Question, Answer, ModelUsed, TokensUsed, QueryUsed, ResponseTimeMS, Created, CreatedBy, Updated, UpdatedBy, IsActive

Or create the table via iDempiere Application Dictionary UI, then Pack Out.

---

### Fix 9: insert_ai_assistant.sql missing AD_Form and AD_Form_Access

**File:** `plugin/insert_ai_assistant.sql`

**Problem:** SQL only creates AD_Process + AD_Menu. Missing: AD_Form, AD_Form_Access. Same issue as Fix 7 but in the SQL file.

**Fix:** Add AD_Form INSERT + AD_Form_Access INSERT. Or remove this SQL file entirely and rely on 2Pack.

---

## ⚠️ MODERATE (should fix)

### Fix 10: MANIFEST.MF Service-Component not using wildcard

**File:** `plugin/META-INF/MANIFEST.MF` line 9

```
# BEFORE:
Service-Component: OSGI-INF/AIAssistantModelFactory.xml, OSGI-INF/AIChatFormFactory.xml

# AFTER:
Service-Component: OSGI-INF/*.xml
```

---

### Fix 11: pom.xml systemPath uses wildcard glob

**File:** `plugin/pom.xml` line 64

**Problem:** `<systemPath>...org.adempiere.pipo_12.0.0.*.jar</systemPath>` — Maven doesn't support wildcard in systemPath.

**Fix:** Specify exact jar name, or use `<scope>provided</scope>` without systemPath (rely on iDempiere parent POM for dependency resolution).

---

### Fix 12: AIChatForm static ExecutorService no shutdown hook

**File:** `plugin/src/idempiere/ai/assistant/form/AIChatForm.java` line 46

**Problem:** `AI_THREAD_POOL` is static, never shut down when OSGi bundle stops. Thread leak.

**Fix:** In `AIAssistantActivator.stop()`:
```java
@Override
public void stop(BundleContext context) throws Exception {
    AIChatForm.shutdownThreadPool();
    super.stop(context);
}
```

And in `AIChatForm.java`:
```java
public static void shutdownThreadPool() {
    AI_THREAD_POOL.shutdown();
}
```

---

### Fix 13: build.sh missing process/ directory

**File:** `plugin/build.sh`

**Problem:** `javac` and `jar` commands don't include `process/` directory. `AIAssistantTestProcess.class` won't be in the JAR.

**Fix:** Add to build.sh compile step:
```bash
# Add to javac sources:
src/idempiere/ai/assistant/process/AIAssistantTestProcess.java

# Add to jar packaging:
idempiere/ai/assistant/process/*.class
```

---

### Fix 14: PackOut.xml UU fields use artificial UUIDs

**File:** `PackOut.xml`

**Problem:** UUIDs like `aa001001-0000-0000-0000-000000000001` are human-crafted, not generated. While not immediately broken, they could conflict if multiple plugins use the same pattern.

**Fix:** Use `uuidgen` or iDempiere's Pack Out tool to generate real UUIDs.

---

## Summary

| Priority | Count | Status |
|----------|-------|--------|
| 🔴 CRITICAL | 5 | Plugin cannot deploy |
| 🟡 IMPORTANT | 4 | Core functionality broken |
| ⚠️ MODERATE | 5 | Quality issues |

**Recommended approach:** Fix CRITICAL #1-3 and #6 first (MANIFEST.MF + 2Pack path + afterPackIn + ModelFactory XML). These are the minimum to get the bundle to resolve and start. Then fix the 2Pack content issues (#5, #7, #8).

## Reference

Brain files used for this review:
- `brain/idempiere-osgi-bundle.md` — MANIFEST.MF rules, DS components
- `brain/idempiere-2pack.md` — ZIP structure, AD_Field rules, afterPackIn
- `brain/idempiere-po-model.md` — @Model, initPO, field types

Skill files used:
- `idempiere-zul-form` — Form registration pattern
- `idempiere-mapped-model-factory-service` — ModelFactory pattern
- `idempiere-osgi-event-handler` — DS component pattern
