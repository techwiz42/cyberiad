```
cyberiad-client/
├── src/
│   ├── components/           # Reusable components
│   │   ├── layout/          # Layout components
│   │   │   ├── Header.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── Footer.tsx
│   │   ├── thread/          # Thread-related components
│   │   │   ├── ThreadList.tsx
│   │   │   ├── ThreadItem.tsx
│   │   │   ├── ThreadCreator.tsx
│   │   │   └── ThreadViewer.tsx
│   │   ├── chat/            # Chat components
│   │   │   ├── MessageList.tsx
│   │   │   ├── MessageItem.tsx
│   │   │   ├── MessageInput.tsx
│   │   │   └── MessageActions.tsx
│   │   ├── agents/          # Agent-related components
│   │   │   ├── AgentList.tsx
│   │   │   ├── AgentCard.tsx
│   │   │   └── AgentResponse.tsx
│   │   └── shared/          # Shared components
│   │       ├── Button.tsx
│   │       ├── Input.tsx
│   │       └── Avatar.tsx
│   ├── hooks/               # Custom hooks
│   │   ├── useWebSocket.ts
│   │   ├── useThread.ts
│   │   └── useAgents.ts
│   ├── services/            # API services
│   │   ├── api.ts
│   │   ├── auth.ts
│   │   └── websocket.ts
│   ├── store/               # State management
│   │   ├── threadStore.ts
│   │   ├── userStore.ts
│   │   └── agentStore.ts
│   ├── types/               # TypeScript types
│   │   ├── thread.ts
│   │   ├── message.ts
│   │   └── agent.ts
│   └── utils/               # Utility functions
│       ├── formatting.ts
│       └── validation.ts
├── public/
├── .env
└── package.json
```

Would you like me to:
1. Create the core components (Thread, Chat, or Agent interfaces)?
2. Set up the WebSocket client implementation?
3. Design the state management system?
4. Create the authentication flow?

Let me know which aspect you'd like to focus on first, and I'll help implement it!
