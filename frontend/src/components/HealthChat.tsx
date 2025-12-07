/**
 * Health Coach Chat Component
 * Multi-turn chat interface with Claude AI health coach
 */

import { useState, useEffect, useRef } from 'react';
import { 
  Send, 
  Bot, 
  User, 
  Loader2, 
  Sparkles,
  Database,
  MessageSquare,
  X,
  Maximize2,
  Minimize2
} from 'lucide-react';

interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  toolsUsed?: string[];
}

interface HealthChatProps {
  wsUrl: string;
  apiUrl: string;
}

const SUGGESTED_QUESTIONS = [
  "How are my vitals looking right now?",
  "What's my wellness score?",
  "Are there any concerning patterns?",
  "How can I improve my HRV?",
  "What do my recent alerts mean?",
];

export function HealthChat({ wsUrl, apiUrl }: HealthChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [currentTools, setCurrentTools] = useState<string[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isThinking]);

  const connect = () => {
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      console.log('[Chat] Connected');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        switch (data.type) {
          case 'session_start':
            setSessionId(data.session_id);
            // Add welcome message
            setMessages([{
              role: 'assistant',
              content: "Hello! I'm TELARA, your AI health coach. I have access to your real-time biometric data and can help you understand your health patterns. What would you like to know?",
              timestamp: new Date(),
            }]);
            break;
            
          case 'thinking':
            setIsThinking(true);
            setCurrentTools([]);
            break;
            
          case 'tool_use':
            setCurrentTools(prev => [...prev, data.tool]);
            break;
            
          case 'response':
            setIsThinking(false);
            setMessages(prev => [...prev, {
              role: 'assistant',
              content: data.content,
              timestamp: new Date(),
              toolsUsed: currentTools.length > 0 ? [...currentTools] : undefined,
            }]);
            setCurrentTools([]);
            break;
            
          case 'error':
            setIsThinking(false);
            setMessages(prev => [...prev, {
              role: 'system',
              content: `Error: ${data.message}`,
              timestamp: new Date(),
            }]);
            break;
        }
      } catch (e) {
        console.error('[Chat] Parse error:', e);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      console.log('[Chat] Disconnected');
      // Attempt reconnect after delay
      setTimeout(connect, 3000);
    };

    ws.onerror = (error) => {
      console.error('[Chat] Error:', error);
    };
  };

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [wsUrl]);

  const sendMessage = () => {
    if (!inputValue.trim() || !wsRef.current || !isConnected) return;

    const userMessage: ChatMessage = {
      role: 'user',
      content: inputValue.trim(),
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    
    wsRef.current.send(JSON.stringify({
      message: inputValue.trim(),
      session_id: sessionId,
    }));

    setInputValue('');
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleSuggestedQuestion = (question: string) => {
    setInputValue(question);
  };

  return (
    <div className={`bg-soc-panel border border-soc-border rounded-lg flex flex-col ${
      isExpanded ? 'fixed inset-4 z-50' : 'h-full'
    }`}>
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-soc-border">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-accent-purple/20 rounded-lg">
            <Sparkles size={16} className="text-accent-purple" />
          </div>
          <div>
            <h3 className="text-sm font-medium">Health Coach</h3>
            <div className="flex items-center gap-1 text-xs text-soc-muted">
              <div className={`w-1.5 h-1.5 rounded-full ${
                isConnected ? 'bg-vital-normal' : 'bg-vital-critical'
              }`} />
              {isConnected ? 'Connected' : 'Disconnected'}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1.5 hover:bg-soc-border rounded transition-colors"
          >
            {isExpanded ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex gap-2 ${
              message.role === 'user' ? 'justify-end' : 'justify-start'
            }`}
          >
            {message.role === 'assistant' && (
              <div className="flex-shrink-0 w-7 h-7 rounded-full bg-accent-purple/20 flex items-center justify-center">
                <Bot size={14} className="text-accent-purple" />
              </div>
            )}
            
            <div className={`max-w-[80%] ${
              message.role === 'user' 
                ? 'bg-accent-cyan/20 rounded-2xl rounded-br-md' 
                : message.role === 'system'
                  ? 'bg-vital-critical/20 rounded-lg'
                  : 'bg-soc-bg rounded-2xl rounded-bl-md'
            } px-3 py-2`}>
              <p className="text-sm whitespace-pre-wrap">{message.content}</p>
              
              {message.toolsUsed && message.toolsUsed.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2 pt-2 border-t border-soc-border/50">
                  {message.toolsUsed.map((tool, i) => (
                    <span 
                      key={i}
                      className="text-[10px] px-1.5 py-0.5 bg-soc-border rounded flex items-center gap-1"
                    >
                      <Database size={10} />
                      {tool.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              )}
            </div>
            
            {message.role === 'user' && (
              <div className="flex-shrink-0 w-7 h-7 rounded-full bg-accent-cyan/20 flex items-center justify-center">
                <User size={14} className="text-accent-cyan" />
              </div>
            )}
          </div>
        ))}

        {/* Thinking indicator */}
        {isThinking && (
          <div className="flex gap-2 items-start">
            <div className="flex-shrink-0 w-7 h-7 rounded-full bg-accent-purple/20 flex items-center justify-center">
              <Bot size={14} className="text-accent-purple" />
            </div>
            <div className="bg-soc-bg rounded-2xl rounded-bl-md px-3 py-2">
              <div className="flex items-center gap-2 text-sm text-soc-muted">
                <Loader2 size={14} className="animate-spin" />
                {currentTools.length > 0 ? (
                  <span>Querying {currentTools[currentTools.length - 1].replace(/_/g, ' ')}...</span>
                ) : (
                  <span>Analyzing your health data...</span>
                )}
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggested questions */}
      {messages.length <= 1 && (
        <div className="px-3 pb-2">
          <div className="text-xs text-soc-muted mb-2">Suggested questions:</div>
          <div className="flex flex-wrap gap-1">
            {SUGGESTED_QUESTIONS.slice(0, 3).map((question, i) => (
              <button
                key={i}
                onClick={() => handleSuggestedQuestion(question)}
                className="text-xs px-2 py-1 bg-soc-bg hover:bg-soc-border rounded-full transition-colors truncate max-w-full"
              >
                {question}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="p-3 border-t border-soc-border">
        <div className="flex gap-2">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask about your health..."
            disabled={!isConnected || isThinking}
            className="flex-1 bg-soc-bg border border-soc-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent-cyan disabled:opacity-50"
          />
          <button
            onClick={sendMessage}
            disabled={!inputValue.trim() || !isConnected || isThinking}
            className="p-2 bg-accent-cyan/20 hover:bg-accent-cyan/30 text-accent-cyan rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}

