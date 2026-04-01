package idempiere.ai.assistant.process;

import java.util.Properties;
import java.util.logging.Level;

import org.compiere.process.ProcessInfoParameter;
import org.compiere.process.SvrProcess;

import idempiere.ai.assistant.service.AIChatService;
import idempiere.ai.assistant.service.AIChatException;
import idempiere.ai.assistant.service.AIChatService.AIChatResponse;

/**
 * Test Process for AI Assistant
 * Use this to test Python AI service integration
 * 
 * How to use:
 * 1. Register this process in iDempiere (Application Dictionary → Process)
 * 2. Add a parameter "Question" (String)
 * 3. Run the process and enter your question
 * 4. The answer will be displayed in the process result
 */
public class AIAssistantTestProcess extends SvrProcess {

    private String p_Question = "";

    @Override
    protected void prepare() {
        ProcessInfoParameter[] para = getParameter();
        for (ProcessInfoParameter element : para) {
            String name = element.getParameterName();
            if (name.equals("Question")) {
                p_Question = (String) element.getParameter();
            }
        }
    }

    @Override
    protected String doIt() throws Exception {
        if (p_Question == null || p_Question.trim().isEmpty()) {
            return "Error: Please enter a question";
        }

        log.info("Testing AI Assistant with question: " + p_Question);

        try {
            AIChatService aiService = new AIChatService();
            Properties ctx = getCtx();
            
            AIChatResponse response = aiService.ask(p_Question, ctx);
            
            StringBuilder result = new StringBuilder();
            result.append("=== AI Assistant Response ===\n\n");
            result.append("Question: ").append(p_Question).append("\n\n");
            result.append("Answer: ").append(response.answer).append("\n\n");
            result.append("Model: ").append(response.modelUsed).append("\n");
            result.append("Tokens: ").append(response.tokensUsed).append("\n");
            result.append("Time: ").append(response.elapsedMs).append(" ms\n");
            
            if (response.queryUsed != null) {
                result.append("Query: ").append(response.queryUsed).append("\n");
            }
            
            log.info("AI Assistant test successful");
            return result.toString();
            
        } catch (AIChatException e) {
            log.log(Level.SEVERE, "AI Assistant error: " + e.getUserMessage(), e);
            return "Error: " + e.getUserMessage();
        } catch (Exception e) {
            log.log(Level.SEVERE, "AI Assistant failed", e);
            return "Error: " + e.getMessage();
        }
    }
}
