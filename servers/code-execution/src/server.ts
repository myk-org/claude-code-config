#!/usr/bin/env node
/**
 * Generic UTCP Code-Mode Server for Multiple MCP Integrations
 *
 * This server dynamically loads all MCP server configurations from the
 * ~/.claude/code-execution-configs/ directory and provides batched TypeScript
 * execution with registered MCP tools.
 */

import '@utcp/mcp';  // Auto-registers MCP plugin
import { CodeModeUtcpClient } from '@utcp/code-mode';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import type { MCPConfigFile } from './types.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Load all MCP configurations from ~/.claude/code-execution-configs/ directory
 */
function loadMCPConfigs(): MCPConfigFile['manual_call_templates'] {
  const homeDir = process.env.HOME || process.env.USERPROFILE || '';
  const configsDir = path.join(homeDir, '.claude', 'code-execution-configs');

  if (!fs.existsSync(configsDir)) {
    throw new Error(`Configs directory not found: ${configsDir}`);
  }

  const configFiles = fs.readdirSync(configsDir).filter(f => f.endsWith('.json'));

  if (configFiles.length === 0) {
    throw new Error('No JSON config files found in ~/.claude/code-execution-configs/ directory');
  }

  const allTemplates: MCPConfigFile['manual_call_templates'] = [];

  for (const file of configFiles) {
    const filePath = path.join(configsDir, file);
    try {
      const content = fs.readFileSync(filePath, 'utf-8');
      const config: MCPConfigFile = JSON.parse(content);

      if (config.manual_call_templates && Array.isArray(config.manual_call_templates)) {
        allTemplates.push(...config.manual_call_templates);
        console.log(`✓ Loaded ${config.manual_call_templates.length} template(s) from ${file}`);
      }
    } catch (error) {
      console.warn(`⚠ Failed to load ${file}:`, error instanceof Error ? error.message : error);
    }
  }

  if (allTemplates.length === 0) {
    throw new Error('No MCP templates found in any config file');
  }

  return allTemplates;
}

/**
 * Main server entry point
 */
async function main() {
  try {
    console.log('Starting Generic UTCP Code-Mode Server...\n');

    // Load all MCP configurations
    console.log('Loading MCP configurations from ~/.claude/code-execution-configs/ directory...');
    const templates = loadMCPConfigs();
    console.log(`\n✓ Found ${templates.length} MCP server template(s)\n`);

    // Create UTCP client
    console.log('Creating UTCP client...');
    const client = await CodeModeUtcpClient.create();
    console.log('✓ UTCP client created\n');

    // Register all MCP servers
    console.log('Registering MCP servers...');
    const registeredServers: string[] = [];

    for (const template of templates) {
      try {
        await client.registerManual(template);
        registeredServers.push(template.name);
        console.log(`✓ Registered: ${template.name}`);
      } catch (error) {
        console.error(`✗ Failed to register ${template.name}:`, error instanceof Error ? error.message : error);
      }
    }

    if (registeredServers.length === 0) {
      throw new Error('No MCP servers were successfully registered');
    }

    console.log();

    // Server is ready
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('✓ Generic UTCP Server is ready!');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');
    console.log(`Registered MCP servers (${registeredServers.length}):`);
    registeredServers.forEach(name => console.log(`  - ${name}`));
    console.log('\nYou can now use the client to execute TypeScript code');
    console.log('with registered MCP tools available as async functions.\n');

    // Export client for programmatic use
    return client;

  } catch (error) {
    console.error('Error starting UTCP server:');
    if (error instanceof Error) {
      console.error(`  ${error.message}`);
      if (error.stack) {
        console.error('\nStack trace:');
        console.error(error.stack);
      }
    } else {
      console.error(error);
    }
    process.exit(1);
  }
}

// Run if executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((error) => {
    console.error('Unhandled error:', error);
    process.exit(1);
  });
}

export { main };
export default main;
