#!/bin/bash
# Simple build script for AI Assistant plugin

PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$PLUGIN_DIR/build"
CLASSES_DIR="$BUILD_DIR/classes"
JAR_DIR="$PLUGIN_DIR/target"

# iDempiere plugins directory
IDEMPIERE_PLUGINS="/opt/idempiere-server/x86_64/plugins"

# Create build directories
mkdir -p "$CLASSES_DIR"
mkdir -p "$JAR_DIR"

# Build classpath from iDempiere plugins
CLASSPATH="$IDEMPIERE_PLUGINS/org.adempiere.base_*.jar"
CLASSPATH="$CLASSPATH:$IDEMPIERE_PLUGINS/org.adempiere.ui.zk_*/"
CLASSPATH="$CLASSPATH:$IDEMPIERE_PLUGINS/zk_*.jar"
CLASSPATH="$CLASSPATH:$IDEMPIERE_PLUGINS/org.zkoss.*.jar"
CLASSPATH="$CLASSPATH:$IDEMPIERE_PLUGINS/org.compiere_*.jar"
CLASSPATH="$CLASSPATH:$IDEMPIERE_PLUGINS/org.osgi.core_*.jar"
CLASSPATH="$CLASSPATH:$IDEMPIERE_PLUGINS/gson-*.jar"
CLASSPATH="$CLASSPATH:$IDEMPIERE_PLUGINS/javax.servlet-api-*.jar"

echo "Compiling Java sources..."

# Compile Java sources
javac -d "$CLASSES_DIR" \
    -cp "$CLASSPATH" \
    -source 17 \
    -target 17 \
    "$PLUGIN_DIR/src/idempiere/ai/assistant/AIAssistantActivator.java" \
    "$PLUGIN_DIR/src/idempiere/ai/assistant/model/MAIChatLog.java" \
    "$PLUGIN_DIR/src/idempiere/ai/assistant/model/AIAssistantModelFactory.java" \
    "$PLUGIN_DIR/src/idempiere/ai/assistant/service/HmacUtil.java" \
    "$PLUGIN_DIR/src/idempiere/ai/assistant/service/AIChatException.java" \
    "$PLUGIN_DIR/src/idempiere/ai/assistant/service/AIChatService.java" \
    "$PLUGIN_DIR/src/idempiere/ai/assistant/form/AIChatForm.java" \
    "$PLUGIN_DIR/src/idempiere/ai/assistant/form/AIChatFormFactory.java"

if [ $? -eq 0 ]; then
    echo "Compilation successful!"
    
    # Create JAR
    echo "Creating JAR file..."
    cd "$CLASSES_DIR"
    jar cf "$JAR_DIR/tw.idempiere.ai.assistant-1.0.0-SNAPSHOT.jar" \
        idempiere/ai/assistant/*.class \
        idempiere/ai/assistant/model/*.class \
        idempiere/ai/assistant/service/*.class \
        idempiere/ai/assistant/form/*.class \
        ../../OSGI-INF/*.xml
    
    # Copy MANIFEST.MF to JAR
    cd "$PLUGIN_DIR"
    cd "$JAR_DIR"
    jar uf tw.idempiere.ai.assistant-1.0.0-SNAPSHOT.jar -C "$PLUGIN_DIR/META-INF" MANIFEST.MF
    
    echo "Build complete! JAR file: $JAR_DIR/tw.idempiere.ai.assistant-1.0.0-SNAPSHOT.jar"
else
    echo "Compilation failed!"
    exit 1
fi
