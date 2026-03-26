export default function Home() {
  return (
    <main className="min-h-screen bg-slate-900 text-white">
      <div className="container mx-auto px-4 py-8">
        <header className="mb-8">
          <h1 className="text-4xl font-bold mb-2">Bruno</h1>
          <p className="text-slate-400">Multi-Agent Bitcoin Trading Bot</p>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h2 className="text-xl font-semibold mb-4 text-emerald-400">System Status</h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-400">Backend API</span>
                <span className="text-emerald-400">● Online</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Ollama LLM</span>
                <span className="text-yellow-400">○ Checking...</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">PostgreSQL</span>
                <span className="text-emerald-400">● Connected</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Redis</span>
                <span className="text-emerald-400">● Connected</span>
              </div>
            </div>
          </div>

          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h2 className="text-xl font-semibold mb-4 text-blue-400">Active Agents</h2>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm">Ingestion Agent</span>
                <span className="px-2 py-1 bg-slate-700 rounded text-xs">Standby</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">Quant Agent</span>
                <span className="px-2 py-1 bg-slate-700 rounded text-xs">Standby</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">Sentiment Agent</span>
                <span className="px-2 py-1 bg-slate-700 rounded text-xs">Standby</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">Risk Agent</span>
                <span className="px-2 py-1 bg-slate-700 rounded text-xs">Standby</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">Execution Agent</span>
                <span className="px-2 py-1 bg-slate-700 rounded text-xs">Paper Trading</span>
              </div>
            </div>
          </div>

          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h2 className="text-xl font-semibold mb-4 text-purple-400">LLM Models</h2>
            <div className="space-y-3">
              <div className="p-3 bg-slate-900 rounded border border-slate-700">
                <div className="font-medium text-sm">qwen2.5:14b</div>
                <div className="text-xs text-slate-400 mt-1">Primary Sentiment & Reasoning</div>
              </div>
              <div className="p-3 bg-slate-900 rounded border border-slate-700">
                <div className="font-medium text-sm">deepseek-r1:14b</div>
                <div className="text-xs text-slate-400 mt-1">Deep Chain-of-Thought Analysis</div>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-8 bg-slate-800 rounded-lg p-6 border border-slate-700">
          <h2 className="text-xl font-semibold mb-4">Trading Overview</h2>
          <p className="text-slate-400 text-sm">
            Dashboard wird aktiviert, sobald die Agenten implementiert sind.
          </p>
        </div>
      </div>
    </main>
  );
}
