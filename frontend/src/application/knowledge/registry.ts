import agentInstall from "../../content/knowledge/agent-install.md?raw";
import agentOperations from "../../content/knowledge/agent-operations.md?raw";
import agentBootstrap from "../../content/knowledge/agent-bootstrap.md?raw";
import backendStart from "../../content/knowledge/backend-start.md?raw";
import composeStart from "../../content/knowledge/compose-start.md?raw";
import truenasFullDisk from "../../content/knowledge/truenas-full-disk.md?raw";

export interface KnowledgeDocument {
  id: string;
  title: string;
  description: string;
  content: string;
}

export const knowledgeDocuments: KnowledgeDocument[] = [
  {
    id: "agent-bootstrap",
    title: "Быстрый onboarding Windows-клиента",
    description: "Скрипт отчёта, создание station и безопасная передача token.",
    content: agentBootstrap,
  },
  {
    id: "backend-start",
    title: "Запуск backend на Windows",
    description: "PowerShell, SQLite и Basic Auth для локальной проверки.",
    content: backendStart,
  },
  {
    id: "compose-start",
    title: "Запуск через Docker Compose",
    description: "PostgreSQL, Redis, backend и frontend в локальном профиле.",
    content: composeStart,
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
  {
    id: "truenas-full-disk",
    title: "TrueNAS: полный диск и clone",
    description: "Source dataset, snapshot/clone и роль admin station.",
    content: truenasFullDisk,
  },
];
