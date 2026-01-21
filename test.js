#!/usr/bin/env node

import { spawn } from "child_process";

// Path to your MCP server script
const MCP_SERVER_SCRIPT = "server.js";

// Spawn the MCP server as a subprocess (stdio)
const server = spawn("node", [MCP_SERVER_SCRIPT], {
  stdio: ["pipe", "pipe", "inherit"],
  env: process.env,
  shell: true,
});

// Listen for stdout from the server
server.stdout.on("data", (data) => {
  try {
    const lines = data.toString().split("\n").filter(Boolean);
    for (const line of lines) {
      const parsed = JSON.parse(line);
      if (parsed.result && Array.isArray(parsed.result)) {
        console.log("Resources exposed by MCP server:");
        parsed.result.forEach((r) => console.log(" -", r));
      } else {
        console.log("Server output:", line);
      }
    }
  } catch (err) {
    // Not JSON, just print
    process.stdout.write(data.toString());
  }
});

// Send the JSON-RPC request to list resources
const requestResources = {
  jsonrpc: "2.0",
  id: 1,
  method: "resources/list",
  params: {},
};

// Write the request as newline-delimited JSON
server.stdin.write(JSON.stringify(requestResources) + "\n");

const requestTools = {
    jsonrpc: "2.0",
    id: 1,
    method: "tools/list",
    params: {},
  };


// Write the request as newline-delimited JSON
server.stdin.write(JSON.stringify(requestTools) + "\n");


// Handle exit
server.on("exit", (code) => {
  process.exit(code);
});
