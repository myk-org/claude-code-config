/**
 * Generic type definitions for UTCP MCP server configurations
 */

export interface MCPServerConfig {
  transport?: 'http' | 'stdio';
  url?: string;
  command?: string;
  args?: string[];
  env?: Record<string, string>;
}

export interface MCPServerTemplate {
  name: string;
  call_template_type: 'mcp';
  config: {
    mcpServers: Record<string, MCPServerConfig>;
  };
}

export interface MCPConfigFile {
  manual_call_templates: MCPServerTemplate[];
  tool_repository?: {
    tool_repository_type: string;
  };
  tool_search_strategy?: {
    tool_search_strategy_type: string;
  };
}
