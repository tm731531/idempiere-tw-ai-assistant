-- Direct SQL to insert AI Assistant Process and Menu
-- Run this as postgres user in idempiere database

-- Insert AD_Process
INSERT INTO AD_Process (
    AD_Process_ID, AD_Process_UU, Name, Description, Help, ClassName,
    IsDirectAccess, IsReport, IsServerProcess, IsUseBPartnerLookup,
    AD_Table_ID, AD_PrintFormat_ID, AD_Workflow_ID, AD_Process_Para_ID,
    AD_Org_ID, AD_Client_ID, IsActive, Created, CreatedBy, Updated, UpdatedBy,
    EntityType, Classname, IsBetaFunctionality, IsForm, IsTransaction,
    IsApplySecurityLevel, RefreshAllAfterExecution, ShowHelp, IsReadWrite,
    IsExcludeFromDashboard, IsApplyRoles, IsApplyOrgs, IsRecursive,
    IsOneInstanceOnly, IsLockEntireTable, IsLegacy
) VALUES (
    54001, generate_uuid(), 'AI Assistant Test', 
    'Test Python AI service integration',
    'Enter your question and get AI-powered answer from Python service',
    'idempiere.ai.assistant.process.AIAssistantTestProcess',
    'N', 'N', 'Y', 'N',
    0, 0, 0, 0,
    0, 0, 'Y', now(), 0, now(), 0,
    'U', 'idempiere.ai.assistant.process.AIAssistantTestProcess', 'N', 'N', 'Y',
    'N', 'N', 'N', 'Y',
    'N', 'N', 'N', 'N',
    'N', 'N', 'N'
) ON CONFLICT (AD_Process_UU) DO NOTHING;

-- Insert AD_Menu
INSERT INTO AD_Menu (
    AD_Menu_ID, AD_Menu_UU, Name, Description, Help, Action,
    AD_Process_ID, AD_Window_ID, AD_Form_ID, AD_Workflow_ID,
    AD_Task_ID, AD_Graph_ID, AD_Reporting_ID, AD_ImpEx_Format_ID,
    AD_Ref_List_ID, AD_Color_ID, AD_Image_ID,
    IsSummary, IsSOTrx, IsReadOnly, IsActive,
    IsCentrallyManaged, IsBetaFunctionality, IsBetaCommunityFunctionality,
    IsHideInMenu, ShowAllRoles, IsExcludeFromDashboard,
    AD_Client_ID, AD_Org_ID, Created, CreatedBy, Updated, UpdatedBy,
    EntityType
) VALUES (
    54001, generate_uuid(), 'AI Assistant',
    'AI-powered Q&A assistant',
    'Ask questions about your ERP data in natural language',
    'P',
    54001, 0, 0, 0,
    0, 0, 0, 0,
    0, 0, 0,
    'N', 'N', 'N', 'Y',
    'N', 'N', 'N',
    'N', 'N', 'N',
    0, 0, now(), 0, now(), 0,
    'U'
) ON CONFLICT (AD_Menu_UU) DO NOTHING;

-- Insert AD_TreeNodeMM (add menu under Tools)
INSERT INTO AD_TreeNodeMM (
    AD_TreeNodeMM_ID, AD_TreeNodeMM_UU, AD_Tree_ID, AD_Menu_ID,
    AD_Menu_ID_Parent, SeqNo, SeqNo_Ind, IsCreateChild,
    AD_Client_ID, AD_Org_ID, IsActive, Created, CreatedBy, Updated, UpdatedBy,
    EntityType
) VALUES (
    54001, generate_uuid(), 10, 54001,
    146, 0, 0, 'N',
    0, 0, 'Y', now(), 0, now(), 0,
    'U'
) ON CONFLICT (AD_TreeNodeMM_UU) DO NOTHING;

-- Grant access to all roles
INSERT INTO AD_Process_Access (
    AD_Process_Access_UU, AD_Client_ID, AD_Org_ID, AD_Role_ID, AD_Process_ID,
    IsActive, Created, CreatedBy, Updated, UpdatedBy, IsReadWrite
)
SELECT generate_uuid(), r.AD_Client_ID, 0, r.AD_Role_ID, 54001, 'Y', now(), 0, now(), 0, 'Y'
FROM AD_Role r
WHERE r.IsActive = 'Y'
AND NOT EXISTS (
    SELECT 1 FROM AD_Process_Access pa
    WHERE pa.AD_Role_ID = r.AD_Role_ID AND pa.AD_Process_ID = 54001
);

INSERT INTO AD_Menu_Access (
    AD_Menu_Access_UU, AD_Client_ID, AD_Org_ID, AD_Role_ID, AD_Menu_ID,
    IsActive, Created, CreatedBy, Updated, UpdatedBy, IsReadWrite
)
SELECT generate_uuid(), r.AD_Client_ID, 0, r.AD_Role_ID, 54001, 'Y', now(), 0, now(), 0, 'Y'
FROM AD_Role r
WHERE r.IsActive = 'Y'
AND NOT EXISTS (
    SELECT 1 FROM AD_Menu_Access ma
    WHERE ma.AD_Role_ID = r.AD_Role_ID AND ma.AD_Menu_ID = 54001
);
