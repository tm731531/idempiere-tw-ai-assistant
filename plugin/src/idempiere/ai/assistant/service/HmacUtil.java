package idempiere.ai.assistant.service;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.util.HexFormat;

/**
 * HMAC-SHA256 utility for authenticating requests to Python AI service.
 */
public class HmacUtil {

    /**
     * Compute HMAC-SHA256 of the given body string.
     * The body MUST be the exact bytes that will be sent as the HTTP request body.
     * 
     * @param body the request body (must be same bytes as sent over HTTP)
     * @param secret the shared secret (must match Python service's HMAC_SECRET)
     * @return hex-encoded HMAC-SHA256 signature
     */
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
