# MCP Chat Example (TypeScript)

A simple React-based chat application demonstrating how to use the `mcpbuilder-ai` TypeScript SDK to interact with MCP-powered AI assistants.

## Features

- **Streaming Chat**: Real-time message streaming with the MCP Chat Client
- **Tool Consent**: Interactive approval/denial for AI tool executions
- **Session Management**: Proper session creation and cleanup
- **Configurable**: Support for custom MCP Client URLs and security parameters
- **Modern UI**: Clean chat interface with message history

## Prerequisites

- Node.js 18+ or Bun
- Access to an MCP Client service (cloud or self-hosted)
- A deployed MCP integration with a deployment ID

## Installation

```bash
# Using npm
npm install

# Using Bun
bun install
```

## Configuration

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

Configure the following environment variables (optional):

```env
# Optional: Override the default MCP Client URL
# If not set, uses the SDK default: https://mcp-client.apichap.com
VITE_MCP_CLIENT_URL=https://mcp-client.apichap.com
```

**Note**: The SDK has a built-in default URL for the cloud service. You only need to set `VITE_MCP_CLIENT_URL` if you're using a self-hosted MCP Client or want to override the default.

## Running the Application

```bash
# Development mode
npm run dev

# Or with Bun
bun run dev
```

Open your browser to `http://localhost:5173`.

## Usage

1. **Enter Project Token**: Provide your project authentication token (required)
2. **Enter Deployment Name**: Provide your MCP deployment name (required)
3. **Optional Settings**: Configure custom MCP Client URL if using on-premise deployment
4. **Connect**: Click "Connect" to establish the WebSocket connection
5. **Send Messages**: Type your messages and interact with the AI assistant
6. **Tool Consent**: When the AI wants to execute tools, approve or deny the requests
7. **Disconnect**: Close the browser or navigate away to disconnect

## Project Structure

```
src/
├── main.tsx                    # Application entry point
├── App.tsx                     # Main application component
├── styles.css                  # Tailwind CSS styles
└── components/
    ├── ConfigForm.tsx          # Configuration form for deployment settings
    ├── ChatInterface.tsx       # Main chat interface with message input
    ├── MessageList.tsx         # Display of chat messages
    └── ToolConsentModal.tsx    # Modal for approving/denying tool executions
```

## SDK Usage Example

```typescript
import { MCPChatClient } from 'mcpbuilder-ai';

// Create a new chat client
const client = new MCPChatClient({
  projectToken: 'your-project-token',    // Required: your project authentication token
  deploymentName: 'your-deployment-name', // Required: your deployment identifier
});

// Set up event handlers
client
  .onToken((token) => {
    process.stdout.write(token);
  })
  .onFinal((text, toolCalls) => {
    console.log('\nDone!');
  })
  .onToolConsentRequest((consentId, tool, args, description) => {
    // Approve or deny tool execution
    client.respondConsent(consentId, true);
  })
  .onError((error) => {
    console.error('Error:', error);
  });

// Connect to the server
await client.connect();

// Send a message
await client.sendMessage('Hello, AI!');

// Clean up when done
await client.disconnect();
```

## Building for Production

```bash
# Build the application
npm run build

# Preview the production build
npm run preview
```

## Related Projects

- [mcpbuilder-ai](../../mcp-integration-sdk/typescript_sdk/) - The TypeScript SDK for MCP integrations
- [Python SDK](../../mcp-integration-sdk/python-sdk/) - Python equivalent of the SDK
- [MCP Olympics Example](../mcp_olympics/) - Python MCP server example

## License

MIT
