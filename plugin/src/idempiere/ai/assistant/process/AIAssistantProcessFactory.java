package idempiere.ai.assistant.process;

import java.util.logging.Level;

import org.adempiere.base.IProcessFactory;
import org.compiere.process.ProcessCall;
import org.compiere.util.CLogger;
import org.osgi.service.component.annotations.Component;

/**
 * Process Factory for AI Assistant plugin.
 * Required because iDempiere's DefaultProcessFactory uses Class.forName() from core bundle's classloader
 * and cannot see classes in plugin bundles (different OSGi classloader).
 * 
 * @see <a href="file:///home/tom/idempiere-tw-invoice-system/src/tw/idempiere/invoice/tax/process/TaiwanProcessFactory.java">TaiwanProcessFactory reference</a>
 */
@Component(immediate = true, service = IProcessFactory.class)
public class AIAssistantProcessFactory implements IProcessFactory {

    private static final CLogger log = CLogger.getCLogger(AIAssistantProcessFactory.class);

    @Override
    public ProcessCall newProcessInstance(String className) {
        if ("idempiere.ai.assistant.process.AIAssistantTestProcess".equals(className)) {
            try {
                return new AIAssistantTestProcess();
            } catch (Exception e) {
                log.log(Level.SEVERE, "Failed to create AIAssistantTestProcess", e);
            }
        }
        return null;  // Not our class — let other factories try
    }
}
