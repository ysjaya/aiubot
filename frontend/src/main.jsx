import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './app.jsx'
import './App.css'

// BUG FIX: Jangan panggil createRoot dua kali!
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
