# 2Pack Generation Instructions

## AI_ChatLog Table Structure

The AI_ChatLog table stores audit trail of all Q&A conversations.

### Table Columns

| Column | Type | Key | Required | Description |
|--------|------|-----|----------|-------------|
| AI_ChatLog_ID | ID | PK | Y | Auto-increment primary key |
| AI_ChatLog_UU | VARCHAR(36) | UUID | Y | Unique identifier (IsUpdateable=Y) |
| AD_Client_ID | TableDir | FK | Y | Tenant |
| AD_Org_ID | TableDir | FK | Y | Organization |
| AD_User_ID | TableDir | FK | Y | User who asked |
| AD_Role_ID | TableDir | FK | Y | User's role |
| SessionID | VARCHAR(36) | - | N | Conversation session UUID |
| Question | Text | - | Y | User's question |
| Answer | Text | - | N | AI's response (with PII restored) |
| ModelUsed | VARCHAR(40) | - | N | sonnet / llama_70b / llama_8b |
| TokensUsed | Integer | - | N | Total tokens consumed |
| QueryUsed | VARCHAR(100) | - | N | Which pre-defined SQL was used |
| ResponseTimeMS | Integer | - | N | Round-trip time in milliseconds |
| Created | DateTime | - | Y | Creation timestamp |
| CreatedBy | Table | FK | Y | Created by user |
| Updated | DateTime | - | Y | Last update timestamp |
| UpdatedBy | Table | FK | Y | Updated by user |
| IsActive | YesNo | - | Y | Active flag |

## Generation Steps

### Option 1: Using Application Dictionary UI

1. Login to iDempiere as System Admin
2. Navigate to: Application Dictionary → Table
3. Create Table `AI_ChatLog`:
   - Name: AI Chat Log
   - TableName: AI_ChatLog
   - Entity Type: U (User defined)
   - Access Level: 3 (Client + Org)
   - IsAuditLog: Y

4. Add Columns (in order):
   - AI_ChatLog_ID (Key=Y, Mandatory=Y)
   - AI_ChatLog_UU (DBColumnName: AI_ChatLog_UU, DBColumnType: UUID, IsUpdateable=Y)
   - AD_Client_ID (Reference: TableDir, Reference Key: 192)
   - AD_Org_ID (Reference: TableDir, Reference Key: 193)
   - AD_User_ID (Reference: TableDir, Reference Key: 138)
   - AD_Role_ID (Reference: TableDir, Reference Key: 197)
   - SessionID (DBColumnName: SessionID, DBColumnType: String, Length: 36)
   - Question (DBColumnName: Question, DBColumnType: Text)
   - Answer (DBColumnName: Answer, DBColumnType: Text)
   - ModelUsed (DBColumnName: ModelUsed, DBColumnType: String, Length: 40)
   - TokensUsed (DBColumnName: TokensUsed, DBColumnType: Integer)
   - QueryUsed (DBColumnName: QueryUsed, DBColumnType: String, Length: 100)
   - ResponseTimeMS (DBColumnName: ResponseTimeMS, DBColumnType: Integer)
   - Created, CreatedBy, Updated, UpdatedBy, IsActive (standard columns)

5. Create Window `AI Chat Log`:
   - Name: AI Chat Log
   - Table: AI_ChatLog
   - Read Only: Y (for viewing)
   - Add Tab with all fields

6. Create Form `AI Chat`:
   - Name: AI Chat
   - ClassName: idempiere.ai.assistant.form.AIChatForm
   - Description: AI-powered Q&A assistant for ERP data

7. Create Menu entry:
   - Name: AI Assistant
   - Action: Form
   - AD_Form: AI Chat
   - Parent Menu: Tools (or appropriate parent)

8. Export using Pack Out:
   - Navigate to: Tools → Pack Out
   - Select package name: `tw_idempiere_ai_assistant`
   - Select version: `1.0.0`
   - Include: Table, Window, Form, Menu, Process (if any)
   - Click "Create PackOut"
   - Download ZIP to: `resources/META-INF/2Pack_1.0.0.zip`

### Option 2: Using SQL + Export

Alternatively, create the table via SQL and export:

```sql
-- Create table
CREATE TABLE AI_ChatLog (
    AI_ChatLog_ID NUMERIC(10) NOT NULL,
    AI_ChatLog_UU VARCHAR(36) NOT NULL,
    AD_Client_ID NUMERIC(10) NOT NULL,
    AD_Org_ID NUMERIC(10) NOT NULL,
    AD_User_ID NUMERIC(10) NOT NULL,
    AD_Role_ID NUMERIC(10) NOT NULL,
    SessionID VARCHAR(36),
    Question TEXT NOT NULL,
    Answer TEXT,
    ModelUsed VARCHAR(40),
    TokensUsed NUMERIC(10),
    QueryUsed VARCHAR(100),
    ResponseTimeMS NUMERIC(10),
    Created TIMESTAMP NOT NULL,
    CreatedBy NUMERIC(10) NOT NULL,
    Updated TIMESTAMP NOT NULL,
    UpdatedBy NUMERIC(10) NOT NULL,
    IsActive CHAR(1) NOT NULL DEFAULT 'Y',
    CONSTRAINT AI_ChatLog_Key PRIMARY KEY (AI_ChatLog_ID)
);

-- Create sequence
CREATE SEQUENCE AI_ChatLog_SEQ START WITH 1000000 INCREMENT BY 1;

-- Create indexes
CREATE INDEX AI_ChatLog_AD_User_ID ON AI_ChatLog(AD_User_ID);
CREATE INDEX AI_ChatLog_AD_Role_ID ON AI_ChatLog(AD_Role_ID);
CREATE INDEX AI_ChatLog_Created ON AI_ChatLog(Created);
```

Then register in AD_Table and export via Pack Out.

## Quality Checklist

Before committing the 2Pack, verify:

```
□ ZIP internal structure: tw_idempiere_ai_assistant/dict/PackOut.xml
□ AI_ChatLog_UU column: IsUpdateable=Y (NOT N, or UUID will be NULL)
□ All AD_Field elements have <SeqNoGrid> matching <SeqNo>
□ All AD_Field elements have <IsDisplayedGrid>Y</IsDisplayedGrid>
□ AD_Form ClassName = "idempiere.ai.assistant.form.AIChatForm" (exact match)
□ Menu entry has correct parent (e.g., under Tools)
□ No stale files in OSGI-INF/ (only ModelFactory + FormFactory XMLs)
```

## Post-install Verification

After deploying and starting iDempiere:

```sql
-- Verify table exists
SELECT count(*) FROM information_schema.tables 
WHERE table_schema='adempiere' AND table_name='ai_chatlog';

-- Verify form registered
SELECT AD_Form_ID, Name, ClassName FROM AD_Form 
WHERE ClassName = 'idempiere.ai.assistant.form.AIChatForm';

-- Verify menu entry
SELECT Name, Action FROM AD_Menu WHERE Name = 'AI Assistant';

-- Verify _UU column is updateable
SELECT ColumnName, IsUpdateable FROM AD_Column 
WHERE AD_Table_ID = (SELECT AD_Table_ID FROM AD_Table WHERE TableName='AI_ChatLog') 
AND ColumnName='AI_ChatLog_UU';
-- Should return: IsUpdateable = 'Y'
```

## File Structure

```
plugin/
└── resources/
    └── META-INF/
        └── 2Pack_1.0.0.zip
            └── tw_idempiere_ai_assistant/
                └── dict/
                    └── PackOut.xml
```

---

**Note:** Since 2Pack XML is verbose (~500 lines) and generated by iDempiere's Pack Out process, 
the implementing agent should use the Application Dictionary UI or SQL approach above, then export.
