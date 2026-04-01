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
        // Grant all active roles access to the AI Assistant menu/process
        // This runs after 2Pack is loaded
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
        if (count > 0) {
            log.info("Granted AI Assistant access to " + count + " roles");
        }
        
        // Also grant menu access
        sql = "INSERT INTO AD_Menu_Access (AD_Menu_Access_UU, AD_Client_ID, AD_Org_ID, "
            + "AD_Role_ID, AD_Menu_ID, IsActive, Created, CreatedBy, Updated, UpdatedBy, IsReadWrite) "
            + "SELECT generate_uuid(), r.AD_Client_ID, 0, r.AD_Role_ID, m.AD_Menu_ID, 'Y', "
            + "now(), 0, now(), 0, 'Y' "
            + "FROM AD_Role r, AD_Menu m "
            + "WHERE m.Name = 'AI Assistant' "
            + "AND r.IsActive = 'Y' "
            + "AND NOT EXISTS (SELECT 1 FROM AD_Menu_Access ma "
            + "  WHERE ma.AD_Role_ID = r.AD_Role_ID AND ma.AD_Menu_ID = m.AD_Menu_ID)";
        
        count = DB.executeUpdate(sql, null);
        if (count > 0) {
            log.info("Granted AI Assistant menu access to " + count + " roles");
        }
    }
}
