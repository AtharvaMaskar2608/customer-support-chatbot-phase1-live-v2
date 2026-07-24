import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '../index.css'
import { PlaygroundApp } from './App'

// Isolated entry (CHO-272): prompt playground — separate from chat + traces.
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <PlaygroundApp />
  </StrictMode>,
)
