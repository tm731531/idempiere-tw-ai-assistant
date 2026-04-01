# 2Pack PackOut.xml Fix — 2026-04-01

## Current Error

```
POSaveFailedException: Failed to save ProcessPara Question
```

## Root Cause

Qwen's PackOut.xml format doesn't match iDempiere's 2Pack SAX parser expectations. Comparing with the WORKING tw-invoice PackOut.xml reveals multiple format differences.

## Key Differences (Qwen's broken XML vs tw-invoice's working XML)

### 1. Missing `type="table"` attribute on elements

```xml
<!-- BROKEN (Qwen): -->
<AD_Process>

<!-- WORKING (tw-invoice): -->
<AD_Process type="table">
```

Every element (`AD_Process`, `AD_Process_Para`, `AD_Menu`, `AD_TreeNodeMM`) must have `type="table"`.

### 2. AD_Process_Para must be NESTED inside AD_Process, not a sibling

```xml
<!-- BROKEN (Qwen) — Para is a sibling of Process: -->
<AD_Process>
    ...
</AD_Process>
<AD_Process_Para>
    ...
</AD_Process_Para>

<!-- WORKING (tw-invoice) — Para is nested INSIDE Process: -->
<AD_Process type="table">
    ...
    <AD_Process_Para type="table">
        ...
    </AD_Process_Para>
</AD_Process>
```

This is why "Failed to save ProcessPara" — the SAX parser couldn't resolve the Process reference because Para was a separate element.

### 3. AD_Process_ID reference format in Para

```xml
<!-- BROKEN (Qwen): -->
<AD_Process_ID>@AD_Process_UU=f47ac10b-...@</AD_Process_ID>

<!-- WORKING (tw-invoice): -->
<AD_Process_ID reference="uuid" reference-key="AD_Process">cc001001-0000-...</AD_Process_ID>
```

The `@...@` syntax is NOT how 2Pack references work. Use `reference="uuid" reference-key="AD_Process"`.

### 4. AD_Reference_ID for Process_Para

```xml
<!-- BROKEN (Qwen): -->
<AD_Reference_ID>10</AD_Reference_ID>

<!-- WORKING (tw-invoice): -->
<AD_Reference_ID reference="id" reference-key="AD_Reference">10</AD_Reference_ID>
```

Even for standard system IDs, you need `reference="id" reference-key="AD_Reference"`.

### 5. Missing AD_Client_ID and AD_Org_ID on every element

```xml
<!-- BROKEN (Qwen) — missing: -->
<AD_Process>
    <AD_Process_UU>...</AD_Process_UU>
    <Name>...</Name>

<!-- WORKING (tw-invoice) — present: -->
<AD_Process type="table">
    <AD_Client_ID reference="id">0</AD_Client_ID>
    <AD_Org_ID reference="id">0</AD_Org_ID>
    ...
```

Every element needs `AD_Client_ID` and `AD_Org_ID`.

---

## Complete Fixed PackOut.xml

Replace the entire PackOut.xml with this (following tw-invoice's working pattern):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<idempiere Name="AI Assistant" Version="1.0.0" idempiereVersion="12.0.0"
    DataBaseVersion="12.0.0" Description="AI-powered Q&amp;A assistant for iDempiere ERP"
    Author="TW iDempiere Community" AuthorEmail="dev@tw-idempiere.org"
    CreatedDate="2026-04-01 00:00:00" UpdatedDate="2026-04-01 00:00:00"
    PackOutVersion="100" UpdateDictionary="true" Client="0">

  <AD_Process type="table">
    <AD_Client_ID reference="id">0</AD_Client_ID>
    <AD_Org_ID reference="id">0</AD_Org_ID>
    <Value>TW_AIAssistantTest</Value>
    <Name>AI Assistant Test</Name>
    <Description>Test Python AI service integration</Description>
    <Help>Enter your question and get AI-powered answer from Python service</Help>
    <IsActive>Y</IsActive>
    <IsBetaFunctionality>N</IsBetaFunctionality>
    <IsReport>N</IsReport>
    <AccessLevel>3</AccessLevel>
    <EntityType>U</EntityType>
    <ClassName>idempiere.ai.assistant.process.AIAssistantTestProcess</ClassName>
    <IsDirectPrint>N</IsDirectPrint>
    <IsProcedure>N</IsProcedure>
    <ShowHelp>Y</ShowHelp>
    <AD_Process_UU>f47ac10b-58cc-4372-a567-0e02b2c3d479</AD_Process_UU>
    <AD_Process_Para type="table">
      <AD_Client_ID reference="id">0</AD_Client_ID>
      <AD_Org_ID reference="id">0</AD_Org_ID>
      <AD_Process_ID reference="uuid" reference-key="AD_Process">f47ac10b-58cc-4372-a567-0e02b2c3d479</AD_Process_ID>
      <SeqNo>10</SeqNo>
      <Name>Question</Name>
      <ColumnName>Question</ColumnName>
      <FieldLength>2000</FieldLength>
      <IsMandatory>Y</IsMandatory>
      <IsRange>N</IsRange>
      <IsActive>Y</IsActive>
      <AD_Reference_ID reference="id" reference-key="AD_Reference">10</AD_Reference_ID>
      <EntityType>U</EntityType>
      <AD_Process_Para_UU>a1b2c3d4-5678-9012-3456-789012345678</AD_Process_Para_UU>
    </AD_Process_Para>
  </AD_Process>

  <AD_Menu type="table">
    <AD_Client_ID reference="id">0</AD_Client_ID>
    <AD_Org_ID reference="id">0</AD_Org_ID>
    <Name>AI Assistant</Name>
    <Description>AI-powered Q&amp;A assistant</Description>
    <Help>Ask questions about your ERP data in natural language</Help>
    <Action>P</Action>
    <AD_Process_ID reference="uuid" reference-key="AD_Process">f47ac10b-58cc-4372-a567-0e02b2c3d479</AD_Process_ID>
    <IsSummary>N</IsSummary>
    <IsSOTrx>N</IsSOTrx>
    <IsReadOnly>N</IsReadOnly>
    <IsActive>Y</IsActive>
    <EntityType>U</EntityType>
    <AD_Menu_UU>b2c3d4e5-6789-0123-4567-890123456789</AD_Menu_UU>
  </AD_Menu>

  <AD_TreeNodeMM type="table">
    <AD_Client_ID reference="id">0</AD_Client_ID>
    <AD_Org_ID reference="id">0</AD_Org_ID>
    <AD_Tree_ID reference="id">10</AD_Tree_ID>
    <Node_ID reference="uuid" reference-key="AD_Menu">b2c3d4e5-6789-0123-4567-890123456789</Node_ID>
    <Parent_ID reference="id">146</Parent_ID>
    <SeqNo>999</SeqNo>
    <IsActive>Y</IsActive>
    <AD_TreeNodeMM_UU>c3d4e5f6-7890-1234-5678-901234567890</AD_TreeNodeMM_UU>
  </AD_TreeNodeMM>

</idempiere>
```

---

## Before Redeploying — Clean Up Failed Install Records

```sql
-- Connect as postgres or adempiere user
DELETE FROM adempiere.ad_package_imp_detail
WHERE ad_package_imp_id IN (
    SELECT ad_package_imp_id FROM adempiere.ad_package_imp
    WHERE name LIKE '%AI%'
);
DELETE FROM adempiere.ad_package_imp WHERE name LIKE '%AI%';

-- Also delete any partially created records from previous failed attempts
DELETE FROM adempiere.ad_treenodemm WHERE ad_treenodemm_uu = 'c3d4e5f6-7890-1234-5678-901234567890';
DELETE FROM adempiere.ad_menu WHERE ad_menu_uu = 'b2c3d4e5-6789-0123-4567-890123456789';
DELETE FROM adempiere.ad_process_para WHERE ad_process_para_uu = 'a1b2c3d4-5678-9012-3456-789012345678';
DELETE FROM adempiere.ad_process WHERE ad_process_uu = 'f47ac10b-58cc-4372-a567-0e02b2c3d479';
```

## Rebuild & Redeploy Steps

```bash
# 1. Create fixed ZIP
cd plugin
mkdir -p /tmp/2pack_fix/tw_idempiere_ai_assistant/dict/
# Save the fixed PackOut.xml above as /tmp/2pack_fix/tw_idempiere_ai_assistant/dict/PackOut.xml
cd /tmp/2pack_fix
zip -r /home/tom/idempiere-tw-ai-assistant/plugin/META-INF/2Pack_1.0.0.zip tw_idempiere_ai_assistant/

# 2. Rebuild JAR
cd /home/tom/idempiere-tw-ai-assistant/plugin
bash build.sh  # or mvn clean package

# 3. Clean up old install records (SQL above)

# 4. Copy JAR to plugins
cp target/*.jar /opt/idempiere-server/x86_64/plugins/  # or wherever the JAR goes

# 5. Restart iDempiere

# 6. Check log for success
tail -20 /opt/idempiere-server/x86_64/log/idempiere.*.log | grep -i "pack"
```

## Key Lesson (adding to Domain Brain)

**2Pack PackOut.xml rules from tw-invoice (working reference):**
1. Every element needs `type="table"` attribute
2. `AD_Process_Para` must be NESTED inside `AD_Process`, not a sibling
3. Every element needs `AD_Client_ID reference="id">0` and `AD_Org_ID reference="id">0`
4. FK references use `reference="uuid" reference-key="AD_Table"` format, NOT `@...@`
5. Standard system references (like AD_Reference_ID=10) still need `reference="id" reference-key="AD_Reference"`
