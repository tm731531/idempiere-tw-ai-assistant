# TreeNode Fix — 2026-04-01

## Error
```
AD_TreeNodeMM [...Parent_ID=146...] unresolved [Parent_ID]
```

## Root Cause

`Parent_ID reference="id">146` — **AD_Menu ID 146 does not exist** in this iDempiere environment. The ID was assumed from a different iDempiere installation.

## Fix

**Remove `AD_TreeNodeMM` entirely.** Use `AD_Menu` with `Parent_ID` instead (same pattern as tw-invoice).

Replace the entire PackOut.xml with this:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<idempiere Name="AI Assistant" Version="1.0.1" idempiereVersion="12.0.0"
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
    <IsServerProcess>Y</IsServerProcess>
    <IsUseBPartnerLookup>N</IsUseBPartnerLookup>
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
    <Parent_ID reference="uuid" reference-key="AD_Menu">1c2b0656-a721-41a5-ad1f-44fe2b4f879e</Parent_ID>
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

</idempiere>
```

### Changes from previous version:
1. **Removed `AD_TreeNodeMM` entirely** — use `Parent_ID` inside `AD_Menu` instead
2. **`Parent_ID` uses UUID reference** to System Admin menu: `1c2b0656-a721-41a5-ad1f-44fe2b4f879e`
3. **Version bumped to `1.0.1`** — forces `Incremental2PackActivator` to re-run (it skips same version)
4. **ZIP filename must also change** to `2Pack_1.0.1.zip`

### Before redeploying:

```sql
-- Clean up any residual from failed installs
SET search_path TO adempiere;
DELETE FROM ad_package_imp_detail WHERE ad_package_imp_id IN (SELECT ad_package_imp_id FROM ad_package_imp WHERE name LIKE '%AI%');
DELETE FROM ad_package_imp WHERE name LIKE '%AI%';
DELETE FROM ad_treenodemm WHERE ad_treenodemm_uu = 'c3d4e5f6-7890-1234-5678-901234567890';
DELETE FROM ad_menu WHERE ad_menu_uu = 'b2c3d4e5-6789-0123-4567-890123456789';
DELETE FROM ad_process_para WHERE ad_process_para_uu = 'a1b2c3d4-5678-9012-3456-789012345678';
DELETE FROM ad_process WHERE ad_process_uu = 'f47ac10b-58cc-4372-a567-0e02b2c3d479';
```

### Rebuild:
```bash
# 1. Save new PackOut.xml
# 2. Create ZIP: 2Pack_1.0.1.zip (NOT 1.0.0 — version must change)
mkdir -p /tmp/2pack_fix/tw_idempiere_ai_assistant/dict/
# save PackOut.xml to /tmp/2pack_fix/tw_idempiere_ai_assistant/dict/PackOut.xml
cd /tmp/2pack_fix && zip -r 2Pack_1.0.1.zip tw_idempiere_ai_assistant/
# Copy to plugin
cp 2Pack_1.0.1.zip /home/tom/idempiere-tw-ai-assistant/plugin/META-INF/
# Remove old version
rm /home/tom/idempiere-tw-ai-assistant/plugin/META-INF/2Pack_1.0.0.zip

# 3. Rebuild JAR + deploy + restart
```

## Lesson (added to Domain Brain)

- AD_Menu_ID values are environment-specific — NEVER assume a numeric ID exists
- Use `Parent_ID reference="uuid" reference-key="AD_Menu">parent-uuid` inside `AD_Menu` element
- Do NOT use `AD_TreeNodeMM` for menu placement — use nested `AD_Menu` with `Parent_ID`
- Always query the target environment's `ad_menu` table to find the correct parent UUID
