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
import java.util.logging.Logger;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import org.compiere.model.MRole;
import org.compiere.util.CLogger;
import org.compiere.util.DB;
import org.compiere.util.Env;

import idempiere.ai.assistant.model.MAIChatLog;

/**
 * AI Chat Service - Bridge between ZK Form and Python AI service.
 * 
 * Responsibilities:
 * - Validate user permission (MRole.getFormAccess)
 * - Get user's accessible org IDs (AD_Role_OrgAccess)
 * - Build HTTP request with HMAC authentication
 * - Call Python service
 * - Parse response
 * - Save audit log (best-effort)
 * - Map HTTP errors to user-friendly Chinese messages
 */
public class AIChatService {

    private static final CLogger log = CLogger.getCLogger(AIChatService.class);
    private static final Gson gson = new Gson();

    // Singleton HttpClient - reuses connections
    private static final HttpClient HTTP_CLIENT = HttpClient.newBuilder()
        .connectTimeout(Duration.ofSeconds(5))
        .build();

    private final String serviceUrl;
    private final String hmacSecret;

    /**
     * Constructor - reads configuration from system properties
     */
    public AIChatService() {
        this.serviceUrl = System.getProperty("AI_SERVICE_URL", "http://localhost:8900");
        this.hmacSecret = System.getProperty("AI_HMAC_SECRET", "");
        if (hmacSecret.isEmpty()) {
            log.severe("AI_HMAC_SECRET system property not set! AI service will refuse requests.");
        }
    }

    /**
     * Validate configuration
     */
    private void validateConfig() throws AIChatException {
        if (hmacSecret.isEmpty()) {
            throw new AIChatException("AI 服務尚未設定，請聯繫管理員設定 AI_HMAC_SECRET");
        }
    }

    /**
     * Ask the AI service a question.
     * 
     * @param question user's question
     * @param ctx iDempiere context
     * @return AI response
     * @throws AIChatException if service unavailable or error occurs
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
        body.addProperty("language", Env.getAD_Language(ctx)); // e.g., "zh_TW"

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

        // Save audit log (best-effort - never blocks answer display)
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
            // Don't throw - always return the answer even if log save fails
        }

        return new AIChatResponse(answer, modelUsed, tokensUsed, queryUsed, elapsedMs);
    }

    /**
     * Call Python AI service via HTTP POST
     */
    private String callService(String jsonBody, String signature) throws AIChatException {
        try {
            HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(serviceUrl + "/v1/ask"))
                .timeout(Duration.ofSeconds(30))  // Must be > Python's 25s timeout
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
                    log.severe("HMAC authentication failed - check AI_HMAC_SECRET");
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

        // Normal role: query AD_Role_OrgAccess (NOT MRole.getOrgAccess() which is private)
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

    // ============== Response DTO ==============

    /**
     * AI Chat Response DTO
     */
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
}
