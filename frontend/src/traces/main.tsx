import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '../index.css'
import { TracesApp } from './App'

// Isolated third entry (CHO-262): the admin trace viewer has its own React root,
// separate from the chat app (main.tsx) and the corner widget.
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <TracesApp />
  </StrictMode>,
)
