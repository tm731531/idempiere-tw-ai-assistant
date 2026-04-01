#!/bin/bash
# Build script for AI Assistant plugin - Core only (no Form UI)

PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$PLUGIN_DIR/build"
CLASSES_DIR="$BUILD_DIR/classes"
JAR_DIR="$PLUGIN_DIR/target"

# iDempiere installation
IDEMPIERE_HOME="/opt/idempiere-server/x86_64"
IDEMPIERE_PLUGINS="$IDEMPIERE_HOME/plugins"

# Create build directories
mkdir -p "$CLASSES_DIR"
mkdir -p "$JAR_DIR"

# Build classpath
CLASSPATH=""
for jar in "$IDEMPIERE_PLUGINS"/*.jar; do
    CLASSPATH="$CLASSPATH:$jar"
done
CLASSPATH="$CLASSPATH:$IDEMPIERE_PLUGINS/org.adempiere.ui.zk_*/"
CLASSPATH="$CLASSPATH:$IDEMPIERE_PLUGINS/zk_*/"

echo "Compiling core classes (no Form UI)..."

# Compile only core classes (no Form)
javac -d "$CLASSES_DIR" \
    -cp "$CLASSPATH" \
    -source 17 \
    -target 17 \
    -encoding UTF-8 \
    "$PLUGIN_DIR/src/idempiere/ai/assistant/AIAssistantActivator.java" \
    "$PLUGIN_DIR/src/idempiere/ai/assistant/model/MAIChatLog.java" \
    "$PLUGIN_DIR/src/idempiere/ai/assistant/model/AIAssistantModelFactory.java" \
    "$PLUGIN_DIR/src/idempiere/ai/assistant/service/HmacUtil.java" \
    "$PLUGIN_DIR/src/idempiere/ai/assistant/service/AIChatException.java" \
    "$PLUGIN_DIR/src/idempiere/ai/assistant/service/AIChatService.java" \
    "$PLUGIN_DIR/src/idempiere/ai/assistant/process/AIAssistantTestProcess.java"

if [ $? -eq 0 ]; then
    echo "Compilation successful!"
    
    # Create JAR
    echo "Creating JAR file..."
    cd "$CLASSES_DIR"
    
    # Create JAR with core classes only
    cd "$CLASSES_DIR"
    jar cfm "$JAR_DIR/tw.idempiere.ai.assistant-1.0.0-SNAPSHOT.jar" \
        "$PLUGIN_DIR/META-INF/MANIFEST.MF" \
        idempiere/ai/assistant/AIAssistantActivator.class \
        idempiere/ai/assistant/model/*.class \
        idempiere/ai/assistant/service/*.class \
        idempiere/ai/assistant/process/*.class
    
    # Add OSGI-INF
    cd "$PLUGIN_DIR"
    jar uf "$JAR_DIR/tw.idempiere.ai.assistant-1.0.0-SNAPSHOT.jar" OSGI-INF/
    
    # Add META-INF (contains 2Pack)
    jar uf "$JAR_DIR/tw.idempiere.ai.assistant-1.0.0-SNAPSHOT.jar" META-INF/
    
    echo ""
    echo "========================================="
    echo "Build complete! (Core only - no Form UI)"
    echo "JAR file: $JAR_DIR/tw.idempiere.ai.assistant-1.0.0-SNAPSHOT.jar"
    echo "========================================="
    echo ""
    echo "Note: This JAR does not include the Form UI."
    echo "To add Form UI, the AIChatForm.java needs to be updated to match your iDempiere's ZK API version."
    echo ""
    echo "To deploy:"
    echo "  cp $JAR_DIR/tw.idempiere.ai.assistant-1.0.0-SNAPSHOT.jar $IDEMPIERE_HOME/plugins/"
else
    echo "Compilation failed!"
    exit 1
fi
