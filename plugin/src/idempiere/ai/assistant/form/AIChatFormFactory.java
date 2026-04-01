package idempiere.ai.assistant.form;

import org.adempiere.webui.factory.IFormFactory;
import org.adempiere.webui.panel.ADForm;
import org.osgi.service.component.annotations.Component;

/**
 * Form Factory for AI Chat Form.
 * Registered as OSGi DS component.
 */
@Component(immediate = true, service = IFormFactory.class)
public class AIChatFormFactory implements IFormFactory {

    @Override
    public ADForm newFormInstance(String formName) {
        if ("idempiere.ai.assistant.form.AIChatForm".equals(formName)) {
            return new AIChatForm();
        }
        return null;
    }
}
