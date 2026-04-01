package idempiere.ai.assistant.model;

import java.sql.ResultSet;
import java.util.Properties;

import org.adempiere.base.Model;
import org.compiere.model.MTable;
import org.compiere.model.PO;
import org.compiere.model.POInfo;

/**
 * PO Model for AI_ChatLog table.
 * Stores audit trail of AI Q&A conversations.
 */
@Model(table = MAIChatLog.Table_Name)
public class MAIChatLog extends PO {

    /** Table Name */
    public static final String Table_Name = "AI_ChatLog";

    /** Table ID */
    private static int tableId = -1;

    /** Column Names */
    public static final String COLUMNNAME_AI_ChatLog_ID = "AI_ChatLog_ID";
    public static final String COLUMNNAME_AI_ChatLog_UU = "AI_ChatLog_UU";
    public static final String COLUMNNAME_AD_Client_ID = "AD_Client_ID";
    public static final String COLUMNNAME_AD_Org_ID = "AD_Org_ID";
    public static final String COLUMNNAME_AD_User_ID = "AD_User_ID";
    public static final String COLUMNNAME_AD_Role_ID = "AD_Role_ID";
    public static final String COLUMNNAME_SessionID = "SessionID";
    public static final String COLUMNNAME_Question = "Question";
    public static final String COLUMNNAME_Answer = "Answer";
    public static final String COLUMNNAME_ModelUsed = "ModelUsed";
    public static final String COLUMNNAME_TokensUsed = "TokensUsed";
    public static final String COLUMNNAME_QueryUsed = "QueryUsed";
    public static final String COLUMNNAME_ResponseTimeMS = "ResponseTimeMS";

    /**
     * Standard Constructor
     */
    public MAIChatLog(Properties ctx, int AI_ChatLog_ID, String trxName) {
        super(ctx, AI_ChatLog_ID, trxName);
    }

    /**
     * Standard Constructor
     */
    public MAIChatLog(Properties ctx, ResultSet rs, String trxName) {
        super(ctx, rs, trxName);
    }

    /**
     * Get Table ID
     */
    public static int getTable_ID() {
        if (tableId <= 0) {
            tableId = MTable.getTable_ID(Table_Name);
        }
        return tableId;
    }

    @Override
    protected int get_AccessLevel() {
        return ACCESSLEVEL_CLIENTORG; // 3 = Client + Org
    }

    @Override
    protected POInfo initPO(Properties ctx) {
        int tableId = getTable_ID();
        if (tableId <= 0) {
            // Guard: 2Pack may not have run yet
            return null;
        }
        return POInfo.getPOInfo(ctx, tableId, get_TrxName());
    }

    /**
     * Set Question
     */
    public void setQuestion(String question) {
        set_Value(COLUMNNAME_Question, question);
    }

    /**
     * Get Question
     */
    public String getQuestion() {
        return (String) get_Value(COLUMNNAME_Question);
    }

    /**
     * Set Answer
     */
    public void setAnswer(String answer) {
        set_Value(COLUMNNAME_Answer, answer);
    }

    /**
     * Get Answer
     */
    public String getAnswer() {
        return (String) get_Value(COLUMNNAME_Answer);
    }

    /**
     * Set Model Used
     */
    public void setModelUsed(String model) {
        set_Value(COLUMNNAME_ModelUsed, model);
    }

    /**
     * Get Model Used
     */
    public String getModelUsed() {
        return (String) get_Value(COLUMNNAME_ModelUsed);
    }

    /**
     * Set Tokens Used
     */
    public void setTokensUsed(int tokens) {
        set_Value(COLUMNNAME_TokensUsed, tokens);
    }

    /**
     * Get Tokens Used
     */
    public int getTokensUsed() {
        Integer ii = (Integer) get_Value(COLUMNNAME_TokensUsed);
        return ii == null ? 0 : ii.intValue();
    }

    /**
     * Set Query Used
     */
    public void setQueryUsed(String query) {
        set_Value(COLUMNNAME_QueryUsed, query);
    }

    /**
     * Get Query Used
     */
    public String getQueryUsed() {
        return (String) get_Value(COLUMNNAME_QueryUsed);
    }

    /**
     * Set Response Time (ms)
     */
    public void setResponseTimeMS(int ms) {
        set_Value(COLUMNNAME_ResponseTimeMS, ms);
    }

    /**
     * Get Response Time (ms)
     */
    public int getResponseTimeMS() {
        Integer ii = (Integer) get_Value(COLUMNNAME_ResponseTimeMS);
        return ii == null ? 0 : ii.intValue();
    }

    /**
     * Set Session ID
     */
    public void setSessionID(String sessionId) {
        set_Value(COLUMNNAME_SessionID, sessionId);
    }

    /**
     * Get Session ID
     */
    public String getSessionID() {
        return (String) get_Value(COLUMNNAME_SessionID);
    }

    /**
     * Set AD User ID
     */
    public void setAD_User_ID(int AD_User_ID) {
        set_Value(COLUMNNAME_AD_User_ID, AD_User_ID);
    }

    /**
     * Get AD User ID
     */
    public int getAD_User_ID() {
        Integer ii = (Integer) get_Value(COLUMNNAME_AD_User_ID);
        return ii == null ? 0 : ii.intValue();
    }

    /**
     * Set AD Role ID
     */
    public void setAD_Role_ID(int AD_Role_ID) {
        set_Value(COLUMNNAME_AD_Role_ID, AD_Role_ID);
    }

    /**
     * Get AD Role ID
     */
    public int getAD_Role_ID() {
        Integer ii = (Integer) get_Value(COLUMNNAME_AD_Role_ID);
        return ii == null ? 0 : ii.intValue();
    }
}
