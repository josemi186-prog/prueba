
import React, { useState, useEffect } from 'react';

interface Props {
  onComplete: (success: boolean) => void;
  type: 'nike' | 'condorito';
}

const LibreroMiniGame: React.FC<Props> = ({ onComplete, type }) => {
  const [input, setInput] = useState('');
  const [timeLeft, setTimeLeft] = useState(15);
  const [isActive, setIsActive] = useState(true);

  useEffect(() => {
    let timer: any;
    if (isActive && timeLeft > 0) {
      timer = setInterval(() => setTimeLeft(prev => prev - 1), 1000);
    } else if (timeLeft === 0) {
      onComplete(false);
    }
    return () => clearInterval(timer);
  }, [timeLeft, isActive]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const correct = type === 'nike' ? 'victoria' : '34'; // Dummy logic
    if (input.toLowerCase().includes(correct)) {
      setIsActive(false);
      onComplete(true);
    } else {
      alert("¡No! JR te está mirando con cara de pocos amigos...");
    }
  };

  return (
    <div className="bg-stone-800 text-white p-8 rounded-2xl shadow-2xl max-w-md mx-auto border-4 border-amber-900">
      <div className="flex justify-between mb-4">
        <span className="text-amber-400 font-bold uppercase tracking-widest">Reto Librero</span>
        <span className="text-red-500 font-mono">00:{timeLeft < 10 ? `0${timeLeft}` : timeLeft}</span>
      </div>
      
      <h2 className="text-2xl font-bold mb-4 serif">
        {type === 'nike' ? 'El Enigma del Libro de Nike' : 'Gestión de Stock: Condorito'}
      </h2>
      
      <p className="mb-6 text-stone-300 italic">
        {type === 'nike' 
          ? "Un cliente pregunta por 'un libro de una marca de tenis'. JM sospecha que es la biografía del fundador de Nike. ¿Cómo se llama la diosa griega que da nombre a la marca?" 
          : "JR viene gritando. Necesitamos saber cuántos ejemplares de Condorito quedan en el sótano antes de que llegue la huelga de transporte."}
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <input 
          autoFocus
          className="w-full p-3 bg-stone-700 rounded border border-stone-600 focus:outline-none focus:ring-2 focus:ring-amber-500"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Escribe tu respuesta..."
        />
        <button className="w-full bg-amber-600 hover:bg-amber-700 py-3 rounded font-bold transition-colors">
          Confirmar en el sistema Agapea
        </button>
      </form>
    </div>
  );
};

export default LibreroMiniGame;
