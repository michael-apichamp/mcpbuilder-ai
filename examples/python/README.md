# Python MCP Integration Examples

This directory contains examples demonstrating how to integrate the MCPBuilder Python SDK
into your Python applications.

## Examples

### [mcp_integration_demo](./mcp_integration_demo/)

A complete example project showing how to:
- Install the SDK from PyPI
- Configure connection settings
- Create a reusable chat service wrapper
- Handle streaming responses and tool executions
- Build an interactive chat interface

## Prerequisites

- Python 3.10 or higher
- Access to an MCP Client Service instance
- A valid deployment name from your MCPBuilder setup

## Quick Start

1. Navigate to the example directory:
   ```bash
   cd mcp_integration_demo
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux/macOS
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Update configuration in `config/settings.py`:
   - Set `DEPLOYMENT_NAME` to your MCPBuilder deployment
   - Set `MCP_SERVICE_URL` to your MCP client service URL

5. Run the example:
   ```bash
   python main.py
   ```

## Installing the SDK

```bash
pip install mcpbuilder-ai==1.0.0
```

## SDK Documentation

For complete SDK documentation, see the [MCPBuilder Python SDK README](../../mcp-integration-sdk/python-sdk/README.md).
