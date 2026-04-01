package idempiere.ai.assistant;

import java.util.logging.Logger;

import org.adempiere.plugin.utils.Incremental2PackActivator;
import org.compiere.util.DB;

/**
 * OSGi Bundle Activator for AI Assistant plugin.
 * Automatically loads 2Pack on first start.
 */
public class AIAssistantActivator extends Incremental2PackActivator {
    
    private static final Logger log = Logger.getLogger(AIAssistantActivator.class.getName());

    @Override
    protected void afterPackIn() {
        // Grant process access to all active roles
        String sql = "INSERT INTO AD_Process_Access (AD_Process_Access_UU, AD_Client_ID, AD_Org_ID, "
            + "AD_Role_ID, AD_Process_ID, IsActive, Created, CreatedBy, Updated, UpdatedBy, IsReadWrite) "
            + "SELECT generate_uuid(), r.AD_Client_ID, 0, r.AD_Role_ID, p.AD_Process_ID, 'Y', "
            + "now(), 0, now(), 0, 'Y' "
            + "FROM AD_Role r, AD_Process p "
            + "WHERE p.ClassName = 'idempiere.ai.assistant.process.AIAssistantTestProcess' "
            + "AND r.IsActive = 'Y' "
            + "AND NOT EXISTS (SELECT 1 FROM AD_Process_Access pa "
            + "  WHERE pa.AD_Role_ID = r.AD_Role_ID AND pa.AD_Process_ID = p.AD_Process_ID)";

        int count = DB.executeUpdate(sql, null);
        log.info("Granted AI Assistant process access to " + count + " roles");

        // Grant form access to all active roles
        // NOTE: There is NO ad_menu_access table in iDempiere.
        // Menu access is controlled through AD_Process_Access and AD_Form_Access.
        sql = "INSERT INTO AD_Form_Access (AD_Form_Access_UU, AD_Client_ID, AD_Org_ID, "
            + "AD_Role_ID, AD_Form_ID, IsActive, Created, CreatedBy, Updated, UpdatedBy, IsReadWrite) "
            + "SELECT generate_uuid(), r.AD_Client_ID, 0, r.AD_Role_ID, f.AD_Form_ID, 'Y', "
            + "now(), 0, now(), 0, 'Y' "
            + "FROM AD_Role r, AD_Form f "
            + "WHERE f.ClassName = 'idempiere.ai.assistant.form.AIChatForm' "
            + "AND r.IsActive = 'Y' "
            + "AND NOT EXISTS (SELECT 1 FROM AD_Form_Access fa "
            + "  WHERE fa.AD_Role_ID = r.AD_Role_ID AND fa.AD_Form_ID = f.AD_Form_ID)";

        count = DB.executeUpdate(sql, null);
        if (count > 0) {
            log.info("Granted AI Chat form access to " + count + " roles");
        }
    }
}
