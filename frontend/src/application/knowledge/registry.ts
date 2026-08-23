import agentInstall from "../../content/knowledge/agent-install.md?raw";
import agentOperations from "../../content/knowledge/agent-operations.md?raw";
import backendStart from "../../content/knowledge/backend-start.md?raw";

export interface KnowledgeDocument {
  id: string;
  title: string;
  description: string;
  content: string;
}

export const knowledgeDocuments: KnowledgeDocument[] = [
  {
    id: "backend-start",
    title: "Запуск backend на Windows",
    description: "PowerShell, SQLite и Basic Auth для локальной проверки.",
    content: backendStart,
  },
  {
    id: "agent-install",
    title: "Установка Windows-агента",
    description: "Enrollment, DPAPI, service account и регистрация службы.",
    content: agentInstall,
  },
  {
    id: "agent-operations",
    title: "Управление агентами",
    description: "Heartbeat, refresh-команды, статусы и диагностика.",
    content: agentOperations,
  },
];
