
import React, { useState, useEffect, useCallback } from 'react';
import { GameState, StoryNode, PlayerStats } from './types';
import { getNextStoryNode } from './geminiService';
import CharacterCard from './components/CharacterCard';
import LibreroMiniGame from './components/LibreroMiniGame';

const App: React.FC = () => {
  const [gameState, setGameState] = useState<GameState>(GameState.START);
  const [currentStory, setCurrentStory] = useState<StoryNode | null>(null);
  const [stats, setStats] = useState<PlayerStats>({
    connection: 20,
    orderLevel: 80,
    humorLevel: 90,
    booksSorted: 0
  });
  const [loading, setLoading] = useState(false);
  const [showMiniGame, setShowMiniGame] = useState(false);

  const loadStory = async (choiceText: string = "Inicio") => {
    setLoading(true);
    try {
      const nextNode = await getNextStoryNode(
        currentStory?.chapter || "1",
        choiceText,
        stats
      );
      setCurrentStory(nextNode);
      setGameState(GameState.STORY);
    } catch (error) {
      console.error("Error loading story:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleChoice = (choice: any) => {
    // Logic to update stats based on choice type
    const newStats = { ...stats };
    if (choice.type === 'intellectual') newStats.connection += 5;
    if (choice.type === 'affectionate') newStats.connection += 10;
    
    // Random chance of mini-game or "desastre"
    if (Math.random() > 0.7) {
      setShowMiniGame(true);
    } else {
      setStats(newStats);
      loadStory(choice.text);
    }
  };

  const handleMiniGameComplete = (success: boolean) => {
    setShowMiniGame(false);
    if (success) {
      setStats(prev => ({ ...prev, connection: prev.connection + 15, booksSorted: prev.booksSorted + 1 }));
      alert("¡Éxito! JR está impresionado. Tu conexión con el catálogo (y con Vero/JM) aumenta.");
    } else {
      alert("¡Desastre! El sistema se ha colgado y JR está echando humo. Pero oye, al menos os habéis reído.");
    }
    loadStory("Tras el lío de los libros");
  };

  if (gameState === GameState.START) {
    return (
      <div className="min-h-screen book-texture flex flex-col items-center justify-center p-6 text-center">
        <div className="max-w-3xl bg-white/80 backdrop-blur shadow-2xl rounded-3xl p-12 border border-amber-100">
          <h1 className="text-6xl font-bold mb-4 serif text-amber-900 leading-tight">
            Agapea: <br/> <span className="text-amber-700 italic">El Catálogo del Destino</span>
          </h1>
          <p className="text-xl text-stone-600 mb-8 max-w-lg mx-auto leading-relaxed">
            Dos historiadores, miles de libros y un fleje de desastres por venir. <br/>
            ¿Lograrán superar la distancia entre Gran Canaria y Málaga?
          </p>
          <button 
            onClick={() => loadStory()}
            className="bg-amber-800 hover:bg-amber-900 text-white px-10 py-4 rounded-full text-xl font-bold transition-all transform hover:scale-105 shadow-xl"
          >
            Abrir el Libro del Destino
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-stone-100 flex flex-col lg:flex-row">
      {/* Sidebar: Status & Characters */}
      <aside className="lg:w-80 bg-stone-200/50 p-6 border-r border-stone-300 flex flex-col gap-6 overflow-y-auto max-h-screen sticky top-0">
        <div className="bg-amber-900 text-white p-4 rounded-lg shadow-inner">
          <h2 className="text-xs uppercase tracking-tighter opacity-70 mb-1">Estado de la Relación</h2>
          <div className="flex items-center gap-3">
            <span className="text-3xl">❤️</span>
            <div className="flex-1">
              <div className="h-3 bg-stone-700 rounded-full overflow-hidden">
                <div className="h-full bg-red-500 transition-all duration-1000" style={{ width: `${Math.min(stats.connection, 100)}%` }}></div>
              </div>
              <span className="text-xs font-bold">{stats.connection}/100 Conexión</span>
            </div>
          </div>
        </div>

        <CharacterCard 
          name="JM" 
          description="1.88m, Barba, fan de los esquemas."
          image="https://picsum.photos/seed/jm/300"
          accentColor="border-blue-600"
          stats={[{ label: 'Orden', value: stats.orderLevel }, { label: 'Paciencia', value: 85 }]}
        />
        
        <CharacterCard 
          name="Vero" 
          description="1.60m, Pelazo rizado, humor canario."
          image="https://picsum.photos/seed/vero/300"
          accentColor="border-amber-500"
          stats={[{ label: 'Humor', value: stats.humorLevel }, { label: 'Energía', value: 95 }]}
        />

        <div className="mt-auto p-4 bg-white/50 rounded-lg text-sm italic text-stone-500 border border-stone-300">
          "La historia no es lo que pasó, sino lo que recordamos juntos."
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 p-6 lg:p-12 overflow-y-auto">
        {loading ? (
          <div className="flex flex-col items-center justify-center h-full">
            <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-amber-800 mb-4"></div>
            <p className="serif text-xl italic text-stone-600">Consultando los archivos de Agapea...</p>
          </div>
        ) : showMiniGame ? (
          <LibreroMiniGame onComplete={handleMiniGameComplete} type={Math.random() > 0.5 ? 'nike' : 'condorito'} />
        ) : currentStory && (
          <div className="max-w-4xl mx-auto">
            <header className="mb-10">
              <div className="flex items-center gap-2 text-amber-700 font-bold mb-2 uppercase tracking-widest text-sm">
                <span>📅 {currentStory.date}</span>
                <span>•</span>
                <span>📍 {currentStory.chapter}</span>
              </div>
              <h1 className="text-5xl font-bold serif text-stone-900 mb-6 leading-tight border-b-2 border-amber-200 pb-4">
                {currentStory.title}
              </h1>
            </header>

            <div className="bg-white p-8 lg:p-12 rounded-3xl shadow-xl border border-stone-200 relative overflow-hidden mb-10">
              {/* Decorative elements */}
              <div className="absolute top-0 right-0 w-32 h-32 bg-amber-50 rounded-bl-full -mr-10 -mt-10 opacity-50"></div>
              
              <p className="text-xl lg:text-2xl leading-relaxed text-stone-800 serif whitespace-pre-wrap">
                {currentStory.text}
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {currentStory.choices.map((choice, index) => (
                <button
                  key={index}
                  onClick={() => handleChoice(choice)}
                  className={`group relative p-6 rounded-2xl border-2 text-left transition-all hover:shadow-xl transform hover:-translate-y-1 active:scale-95
                    ${choice.type === 'intellectual' ? 'border-blue-100 bg-blue-50 hover:border-blue-300' : 
                      choice.type === 'affectionate' ? 'border-pink-100 bg-pink-50 hover:border-pink-300' : 
                      'border-stone-200 bg-white hover:border-stone-400'}`}
                >
                  <div className="flex items-center gap-3 mb-2">
                    <span className="text-2xl">
                      {choice.type === 'intellectual' ? '📜' : choice.type === 'affectionate' ? '✨' : '⚡'}
                    </span>
                    <span className="text-xs uppercase font-bold tracking-widest text-stone-400">
                      {choice.type}
                    </span>
                  </div>
                  <span className="text-lg font-bold text-stone-800 leading-tight">
                    {choice.text}
                  </span>
                  <div className="mt-2 text-xs text-stone-500 opacity-0 group-hover:opacity-100 transition-opacity italic">
                    {choice.consequence || "Tu decisión dará forma al catálogo..."}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default App;
