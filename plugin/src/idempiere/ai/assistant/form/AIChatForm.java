package idempiere.ai.assistant.form;

import java.util.Properties;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.logging.Level;
import java.util.logging.Logger;

import org.adempiere.webui.panel.ADForm;
import org.adempiere.webui.util.ServerPushTemplate;
import org.adempiere.webui.util.ZkContextRunnable;
import org.compiere.util.Env;
import org.zkoss.zk.ui.Desktop;
import org.zkoss.zk.ui.event.Event;
import org.zkoss.zk.ui.event.EventListener;
import org.zkoss.zk.ui.util.DesktopCleanup;
import org.zkoss.zul.Borderlayout;
import org.zkoss.zul.Center;
import org.zkoss.zul.Div;
import org.zkoss.zul.Hbox;
import org.zkoss.zul.Html;
import org.zkoss.zul.South;
import org.zkoss.zul.Textbox;
import org.zkoss.zul.Button;

import idempiere.ai.assistant.service.AIChatService;
import idempiere.ai.assistant.service.AIChatException;

/**
 * AI Chat Form - ZK-based chat UI for AI assistant.
 * 
 * Features:
 * - Chat panel with message bubbles
 * - Input textbox + send button
 * - Loading state with spinner
 * - Background thread processing (isolated thread pool)
 * - ServerPush for real-time updates
 */
public class AIChatForm extends ADForm {

    private static final long serialVersionUID = 1L;
    private static final Logger log = Logger.getLogger(AIChatForm.class.getName());

    // Isolated thread pool - NOT using Adempiere.getThreadPoolExecutor()
    // AI requests can take up to 30s and would starve scheduled processes
    private static final ExecutorService AI_THREAD_POOL = Executors.newFixedThreadPool(4);

    // UI Components
    private Div chatPanel;
    private Textbox inputBox;
    private Button btnSend;
    private volatile boolean formClosed = false;

    // Service
    private AIChatService aiService;

    @Override
    protected void initForm() {
        // Initialize service
        aiService = new AIChatService();

        // Main layout
        Borderlayout layout = new Borderlayout();
        layout.setWidth("100%");
        layout.setHeight("100%");
        appendChild(layout);

        // Center: Chat panel
        Center center = new Center();
        center.setAutoscroll(true);
        layout.appendChild(center);

        chatPanel = new Div();
        chatPanel.setStyle("padding: 10px; overflow-y: auto; height: 400px; background: #f5f5f5;");
        center.appendChild(chatPanel);

        // South: Input area
        South south = new South();
        south.setHeight("80px");
        south.setCollapsible(false);
        layout.appendChild(south);

        Hbox inputArea = new Hbox();
        inputArea.setWidth("100%");
        inputArea.setSpacing("5px");
        inputArea.setStyle("padding: 10px;");
        south.appendChild(inputArea);

        inputBox = new Textbox();
        inputBox.setHflex("1");
        inputBox.setPlaceholder("輸入您的問題，例如：上個月營收最高的客戶是誰？");
        inputBox.setRows(2);
        inputArea.appendChild(inputBox);

        btnSend = new Button("發送");
        btnSend.setStyle("min-width: 80px; height: 100%;");
        inputArea.appendChild(btnSend);

        // Event listeners
        btnSend.addEventListener("onClick", new EventListener<Event>() {
            @Override
            public void onEvent(Event event) {
                sendQuestion();
            }
        });

        inputBox.addEventListener("onOK", new EventListener<Event>() {
            @Override
            public void onEvent(Event event) {
                sendQuestion();
            }
        });

        // Desktop cleanup guard
        getDesktop().addListener(new DesktopCleanup() {
            @Override
            public void cleanup(Desktop desktop) throws Exception {
                formClosed = true;
            }
        });

        // Welcome message
        appendMessage("AI", "歡迎使用 AI 助理！請問有什麼可以幫您？");
    }

    /**
     * Send question to AI service
     */
    private void sendQuestion() {
        String question = inputBox.getText().trim();
        if (question.isEmpty()) {
            return;
        }

        // Disable UI
        btnSend.setDisabled(true);
        inputBox.setDisabled(true);

        // Show user's question
        appendMessage("您", question);

        // Show loading message
        appendMessage("AI", "AI 思考中...");

        // Get context
        Properties ctx = Env.getCtx();

        // Run in background thread (isolated pool)
        AI_THREAD_POOL.submit(new ZkContextRunnable() {
            @Override
            protected void doRun() {
                // Guard against form closed
                if (formClosed) {
                    return;
                }

                try {
                    // Call AI service
                    AIChatService.AIChatResponse response = aiService.ask(question, ctx);

                    // Push result to UI thread
                    ServerPushTemplate template = new ServerPushTemplate(getDesktop());
                    template.executeAsync(new Runnable() {
                        @Override
                        public void run() {
                            // Remove loading message and show answer
                            if (!formClosed) {
                                // Clear last message (loading)
                                if (chatPanel.getChildren().size() > 0) {
                                    chatPanel.getChildren().remove(chatPanel.getChildren().size() - 1);
                                }
                                appendMessage("AI", response.answer);
                            }
                        }
                    });

                } catch (AIChatException e) {
                    // User-friendly error message
                    ServerPushTemplate template = new ServerPushTemplate(getDesktop());
                    try {
                        template.executeAsync(new Runnable() {
                            @Override
                            public void run() {
                                if (!formClosed) {
                                    // Clear last message (loading)
                                    if (chatPanel.getChildren().size() > 0) {
                                        chatPanel.getChildren().remove(chatPanel.getChildren().size() - 1);
                                    }
                                    appendMessage("AI", "錯誤：" + e.getUserMessage());
                                }
                            }
                        });
                    } catch (Exception ex) {
                        log.log(Level.SEVERE, "Failed to push error", ex);
                    }
                } catch (Exception e) {
                    log.log(Level.SEVERE, "AI request failed", e);
                } finally {
                    // Re-enable UI
                    ServerPushTemplate template = new ServerPushTemplate(getDesktop());
                    try {
                        template.executeAsync(new Runnable() {
                            @Override
                            public void run() {
                                if (!formClosed) {
                                    btnSend.setDisabled(false);
                                    inputBox.setDisabled(false);
                                    inputBox.setFocus(true);
                                }
                            }
                        });
                    } catch (Exception e) {
                        log.log(Level.SEVERE, "Failed to re-enable UI", e);
                    }
                }
            }
        });
    }

    /**
     * Append message to chat panel
     */
    private void appendMessage(String sender, String text) {
        String bgColor = "您".equals(sender) ? "#DCF8C6" : "#FFFFFF";
        String align = "您".equals(sender) ? "right" : "left";

        Html bubble = new Html(String.format(
            "<div style='text-align:%s; margin:5px 0;'>" +
            "<div style='display:inline-block; max-width:80%%; padding:8px 12px; " +
            "border-radius:12px; background:%s; text-align:left; box-shadow:0 1px 2px rgba(0,0,0,0.1);'>" +
            "<b>%s:</b><br/>%s</div></div>",
            align, bgColor, sender, escapeHtml(text)
        ));
        chatPanel.appendChild(bubble);

        // Scroll to bottom
        chatPanel.getParent().scrollTo(0, chatPanel.getParent().getClientHeight());
    }

    /**
     * Escape HTML special characters
     */
    private String escapeHtml(String text) {
        return text.replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;")
                   .replace("\"", "&quot;")
                   .replace("'", "&#39;");
    }
}
