package idempiere.ai.assistant.service;

/**
 * Custom exception for AI Chat service errors.
 * Contains user-friendly error messages in Chinese.
 */
public class AIChatException extends Exception {

    private static final long serialVersionUID = 1L;

    private final String userMessage;

    /**
     * Create AI Chat exception with user-friendly message
     * 
     * @param userMessage message to display to user (in Chinese)
     */
    public AIChatException(String userMessage) {
        super(userMessage);
        this.userMessage = userMessage;
    }

    /**
     * Get user-friendly message
     */
    public String getUserMessage() {
        return userMessage;
    }
}
