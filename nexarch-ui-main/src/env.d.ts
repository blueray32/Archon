/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_HOST: string;
  readonly VITE_PORT: string;
  readonly VITE_ENABLE_CHATKIT?: string;
  readonly VITE_CHATKIT_WORKFLOW_ID?: string;
  // Add other environment variables here as needed
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
