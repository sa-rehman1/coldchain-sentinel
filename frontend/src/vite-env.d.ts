/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_CONTROL_TOWER_DATA_SOURCE?: 'mock' | 'api';
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
