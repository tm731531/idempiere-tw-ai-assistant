package idempiere.ai.assistant;

import org.adempiere.plugin.utils.Incremental2PackActivator;
import org.compiere.util.DB;

import java.util.logging.Logger;

/**
 * OSGi Bundle Activator for AI Assistant plugin.
 * Uses Incremental2PackActivator to load 2Pack on first start.
 */
public class AIAssistantActivator extends Incremental2PackActivator {
    
    private static final Logger log = Logger.getLogger(AIAssistantActivator.class.getName());

    @Override
    protected void afterPackIn() {
        // Grant all active roles access to the AI Chat form
        // Without this, no role can open the form after install
        String sql = "INSERT INTO AD_Form_Access (AD_Form_Access_UU, AD_Client_ID, AD_Org_ID, "
            + "AD_Role_ID, AD_Form_ID, IsActive, Created, CreatedBy, Updated, UpdatedBy, IsReadWrite) "
            + "SELECT generate_uuid(), r.AD_Client_ID, 0, r.AD_Role_ID, f.AD_Form_ID, 'Y', "
            + "now(), 0, now(), 0, 'Y' "
            + "FROM AD_Role r, AD_Form f "
            + "WHERE f.ClassName = 'idempiere.ai.assistant.form.AIChatForm' "
            + "AND r.IsActive = 'Y' "
            + "AND NOT EXISTS (SELECT 1 FROM AD_Form_Access fa "
            + "  WHERE fa.AD_Role_ID = r.AD_Role_ID AND fa.AD_Form_ID = f.AD_Form_ID)";
        
        int count = DB.executeUpdate(sql, null);
        if (count > 0) {
            log.info("Granted AI Chat form access to " + count + " roles");
        }
    }
}
