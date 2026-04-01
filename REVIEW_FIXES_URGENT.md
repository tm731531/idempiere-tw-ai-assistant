# URGENT Plugin Fixes — 2026-04-01

Plugin fails to start. Two root causes found from iDempiere log.

---

## Error 1: `ad_menu_access` table does not exist

**Log:**
```
PSQLException: ERROR: relation "ad_menu_access" does not exist
at AIAssistantActivator.afterPackIn(AIAssistantActivator.java:43)
```

**Root cause:** iDempiere does NOT have an `ad_menu_access` table. Menu access is controlled indirectly through `AD_Window_Access`, `AD_Process_Access`, and `AD_Form_Access`. The `INSERT INTO AD_Menu_Access` SQL in `afterPackIn()` is invalid.

**Fix:** `plugin/src/idempiere/ai/assistant/AIAssistantActivator.java`

Remove the entire `AD_Menu_Access` SQL block (lines 32-44). Only keep `AD_Process_Access` and `AD_Form_Access`.

```java
@Override
protected void afterPackIn() {
    // Grant process access
    String sql = "INSERT INTO AD_Process_Access (AD_Process_Access_UU, AD_Client_ID, AD_Org_ID, "
        + "AD_Role_ID, AD_Process_ID, IsActive, Created, CreatedBy, Updated, UpdatedBy, IsReadWrite) "
        + "SELECT generate_uuid(), r.AD_Client_ID, 0, r.AD_Role_ID, p.AD_Process_ID, 'Y', "
        + "now(), 0, now(), 0, 'Y' "
        + "FROM AD_Role r, AD_Process p "
        + "WHERE p.ClassName = 'idempiere.ai.assistant.process.AIAssistantTestProcess' "
        + "AND r.IsActive = 'Y' "
        + "AND NOT EXISTS (SELECT 1 FROM AD_Process_Access pa "
        + "  WHERE pa.AD_Role_ID = r.AD_Role_ID AND pa.AD_Process_ID = p.AD_Process_ID)";
    int count = DB.executeUpdate(sql, null);
    log.info("Granted AI Assistant process access to " + count + " roles");

    // Grant form access (AD_Form_Access DOES exist)
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

    // NOTE: There is NO ad_menu_access table in iDempiere.
    // Menu access is controlled through AD_Window/Process/Form_Access.
}
```

---

## Error 2: 2Pack resolve fails — hardcoded numeric IDs

**Log:**
```
ReferenceUtils.resolveReference → "table" is null
Cannot invoke "org.compiere.model.MTable.isUUIDKeyTable()" because "table" is null
Pack in failed.
```

**Root cause:** PackOut.xml uses `reference="id"` with hardcoded numbers like `54001`:
```xml
<AD_Process_ID reference="id">54001</AD_Process_ID>
```

iDempiere's `ReferenceUtils.resolveReference()` tries to look up the record by numeric ID. For elements like `AD_Table_ID reference="id">0` and `AD_PrintFormat_ID reference="id">0`, it resolves ID 0 → null table → NPE.

**The real problem is all the `reference="id">0` entries.** Many FK columns have `reference="id">0` which means "no reference" but 2Pack tries to resolve them and fails.

**Fix:** Completely rewrite PackOut.xml. The easiest approach:

### Option A: Create dictionary via iDempiere UI, then Pack Out (RECOMMENDED)

1. Start iDempiere without the plugin
2. Login as System Admin
3. Application Dictionary → Process window:
   - Create process "AI Assistant Test"
   - ClassName: `idempiere.ai.assistant.process.AIAssistantTestProcess`
   - Add parameter "Question" (String, Mandatory)
4. Menu → create "AI Assistant" entry under Tools
   - Action: Process
   - Link to the process created above
5. Use Pack Out to export:
   - Type: Process + Menu
   - Export to ZIP
6. Replace `2Pack_1.0.0.zip` with the exported ZIP

This generates correct XML with UUID references and proper element structure.

### Option B: Minimal PackOut.xml that actually works

If you must write XML manually, strip all `reference="id">0` entries and use only required fields:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<idempiere Name="AI Assistant" Version="1.0.0"
    idempiereVersion="12.0.0" DataBaseVersion="12.0.0"
    Description="AI Assistant Plugin"
    Author="TW" CreatedDate="2026-04-01"
    UpdatedDate="2026-04-01" PackOutVersion="100"
    UpdateDictionary="true" Client="0">

    <AD_Process AD_Process_UU="f47ac10b-58cc-4372-a567-0e02b2c3d479"
        Action="Insert">
        <Name>AI Assistant Test</Name>
        <Value>AIAssistantTest</Value>
        <Description>Test Python AI service</Description>
        <Classname>idempiere.ai.assistant.process.AIAssistantTestProcess</Classname>
        <IsReport>false</IsReport>
        <IsDirectPrint>false</IsDirectPrint>
        <AccessLevel>3</AccessLevel>
        <EntityType>U</EntityType>
        <ShowHelp>Y</ShowHelp>
    </AD_Process>

    <AD_Process_Para AD_Process_Para_UU="a1b2c3d4-5678-9012-3456-789012345678"
        Action="Insert">
        <AD_Process_ID AD_Process_UU="f47ac10b-58cc-4372-a567-0e02b2c3d479"/>
        <Name>Question</Name>
        <ColumnName>Question</ColumnName>
        <AD_Reference_ID>10</AD_Reference_ID>
        <FieldLength>2000</FieldLength>
        <IsMandatory>true</IsMandatory>
        <IsRange>false</IsRange>
        <SeqNo>10</SeqNo>
        <EntityType>U</EntityType>
    </AD_Process_Para>

    <AD_Menu AD_Menu_UU="b2c3d4e5-6789-0123-4567-890123456789"
        Action="Insert">
        <Name>AI Assistant</Name>
        <Description>AI-powered Q&amp;A</Description>
        <Action>P</Action>
        <AD_Process_ID AD_Process_UU="f47ac10b-58cc-4372-a567-0e02b2c3d479"/>
        <IsSummary>false</IsSummary>
        <IsSOTrx>false</IsSOTrx>
        <IsReadOnly>false</IsReadOnly>
        <EntityType>U</EntityType>
    </AD_Menu>

    <AD_TreeNodeMM AD_TreeNodeMM_UU="c3d4e5f6-7890-1234-5678-901234567890"
        Action="Insert">
        <AD_Tree_ID>10</AD_Tree_ID>
        <Node_ID AD_Menu_UU="b2c3d4e5-6789-0123-4567-890123456789"/>
        <Parent_ID>146</Parent_ID>
        <SeqNo>999</SeqNo>
    </AD_TreeNodeMM>

</idempiere>
```

**IMPORTANT:** The UUIDs above are examples. Generate real ones with `uuidgen`.

---

## After fixing, clean up previous failed install

Before redeploying, clean up the failed 2Pack records:

```sql
-- Run as adempiere user
DELETE FROM adempiere.ad_package_imp_detail
WHERE ad_package_imp_id IN (
    SELECT ad_package_imp_id FROM adempiere.ad_package_imp
    WHERE name LIKE '%AI%'
);
DELETE FROM adempiere.ad_package_imp WHERE name LIKE '%AI%';
```

Then restart iDempiere with the fixed JAR.

---

## Verification after fix

```sql
-- Check process registered
SELECT ad_process_id, name, classname FROM adempiere.ad_process
WHERE classname LIKE '%AIAssistant%';

-- Check menu entry
SELECT name, action FROM adempiere.ad_menu WHERE name = 'AI Assistant';

-- Check 2Pack completed
SELECT name, pk_status FROM adempiere.ad_package_imp WHERE name LIKE '%AI%';
```
