import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ConfigProvider } from 'antd'
import App from './App'
import './styles/global.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <ConfigProvider
          theme={{
            token: {
              colorPrimary: '#6366f1',
              borderRadius: 10,
              fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
              colorBgContainer: '#ffffff',
              colorBorder: '#e8eaf0',
              colorBorderSecondary: '#f1f3f8',
            },
            components: {
              Button: {
                borderRadius: 8,
                controlHeight: 36,
              },
              Input: {
                borderRadius: 10,
                controlHeight: 40,
              },
              Select: {
                borderRadius: 10,
                controlHeight: 40,
              },
              Card: {
                borderRadiusLG: 16,
              },
              Table: {
                borderRadius: 16,
                borderRadiusLG: 16,
              },
              Modal: {
                borderRadiusLG: 16,
              },
            },
          }}
        >
          <App />
        </ConfigProvider>
      </QueryClientProvider>
    </BrowserRouter>
  </React.StrictMode>
)
