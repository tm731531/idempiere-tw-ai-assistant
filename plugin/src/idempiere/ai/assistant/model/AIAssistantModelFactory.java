package idempiere.ai.assistant.model;

import org.adempiere.base.AnnotationBasedModelFactory;
import org.adempiere.base.IModelFactory;
import org.osgi.service.component.annotations.Component;

/**
 * Model Factory for AI Assistant PO models.
 * Scans the model package for @Model annotations.
 */
@Component(immediate = true, service = IModelFactory.class)
public class AIAssistantModelFactory extends AnnotationBasedModelFactory {

    @Override
    protected String[] getPackages() {
        return new String[] {
            "idempiere.ai.assistant.model"
        };
    }
}
