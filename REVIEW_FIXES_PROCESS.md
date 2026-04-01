# Process Factory Fix — 2026-04-02

## Error
```
Failed to create new process instance for idempiere.ai.assistant.process.AIAssistantTestProcess
```

## Root Cause

iDempiere's `DefaultProcessFactory` uses `Class.forName()` from the **core bundle's classloader**. It cannot see classes in plugin bundles (different OSGi classloader). Every plugin that provides `SvrProcess` subclasses **MUST** implement `IProcessFactory` as an OSGi DS component.

This is documented in Domain Brain (`brain/idempiere-osgi-bundle.md`):
> `DefaultProcessFactory` uses `Class.forName()` from core classloader → cannot find plugin classes → must implement `IProcessFactory`

## Fix — 3 files to create/modify

### 1. Create `AIAssistantProcessFactory.java`

**File:** `plugin/src/idempiere/ai/assistant/process/AIAssistantProcessFactory.java`

```java
package idempiere.ai.assistant.process;

import java.util.logging.Level;

import org.adempiere.base.IProcessFactory;
import org.compiere.process.ProcessCall;
import org.compiere.util.CLogger;
import org.osgi.service.component.annotations.Component;

@Component(immediate = true, service = IProcessFactory.class)
public class AIAssistantProcessFactory implements IProcessFactory {

    private static final CLogger log = CLogger.getCLogger(AIAssistantProcessFactory.class);

    @Override
    public ProcessCall newProcessInstance(String className) {
        if ("idempiere.ai.assistant.process.AIAssistantTestProcess".equals(className)) {
            try {
                return new AIAssistantTestProcess();
            } catch (Exception e) {
                log.log(Level.SEVERE, "Failed to create AIAssistantTestProcess", e);
            }
        }
        return null;  // Not our class — let other factories try
    }
}
```

### 2. Create `OSGI-INF/AIAssistantProcessFactory.xml`

**File:** `plugin/OSGI-INF/AIAssistantProcessFactory.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<scr:component xmlns:scr="http://www.osgi.org/xmlns/scr/v1.1.0"
    name="idempiere.ai.assistant.process.AIAssistantProcessFactory"
    immediate="true">
    <implementation class="idempiere.ai.assistant.process.AIAssistantProcessFactory"/>
    <service>
        <provide interface="org.adempiere.base.IProcessFactory"/>
    </service>
</scr:component>
```

### 3. Add to MANIFEST.MF (if not using wildcard)

If MANIFEST.MF uses explicit Service-Component (not wildcard), add:
```
Service-Component: OSGI-INF/AIAssistantModelFactory.xml,
 OSGI-INF/AIChatFormFactory.xml,
 OSGI-INF/AIAssistantProcessFactory.xml
```

If already using `OSGI-INF/*.xml` wildcard, no change needed — it will be auto-discovered.

### 4. Add to build.sh

Make sure `javac` compiles and `jar` packages the new file:
```bash
# Add to javac:
src/idempiere/ai/assistant/process/AIAssistantProcessFactory.java

# Add to jar:
idempiere/ai/assistant/process/*.class
```

## After Fix

1. Rebuild JAR
2. Copy to plugins/
3. Restart iDempiere (or OSGi refresh)
4. Login → System Admin → AI Assistant → should now open the process dialog

## Reference

Same pattern as tw-invoice: `/home/tom/idempiere-tw-invoice-system/src/tw/idempiere/invoice/tax/process/TaiwanProcessFactory.java`
