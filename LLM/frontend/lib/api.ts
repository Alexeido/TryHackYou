import axios from 'axios';

// Detectamos si estamos en Docker o Localhost
// NEXT_PUBLIC_API_URL se define en el .env, si no, usa localhost
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Tipos de datos para TypeScript (Espejo de tu Backend Python)
export interface ChatMessage {
  role: 'user' | 'assistant' | 'system' | 'tool';
  content?: string;
  tool_calls?: any[];
  tool_call_id?: string;
  name?: string;
}

export interface ChatRequest {
  provider: string;
  api_key: string;
  model_id: string;
  messages: ChatMessage[];
  tools?: any[];
}

export interface ModelInfo {
  id: string;
  provider: string;
  name: string;
  elo_score: number;
  context_window: number;
  pricing_input: number;
  pricing_output: number;
  details: any;
}