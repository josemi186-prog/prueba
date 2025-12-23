
import React from 'react';

interface CharacterCardProps {
  name: string;
  description: string;
  image: string;
  stats: { label: string; value: number }[];
  accentColor: string;
}

const CharacterCard: React.FC<CharacterCardProps> = ({ name, description, image, stats, accentColor }) => {
  return (
    <div className={`bg-white rounded-xl shadow-lg p-4 border-t-4 ${accentColor} transition-all hover:scale-105`}>
      <img src={image} alt={name} className="w-24 h-24 rounded-full mx-auto mb-3 object-cover border-2 border-gray-100" />
      <h3 className="text-xl font-bold text-center serif">{name}</h3>
      <p className="text-sm text-gray-600 text-center mb-4">{description}</p>
      <div className="space-y-2">
        {stats.map((s, i) => (
          <div key={i} className="flex justify-between items-center text-xs">
            <span className="text-gray-500 uppercase tracking-wider">{s.label}</span>
            <div className="w-24 h-2 bg-gray-100 rounded-full overflow-hidden">
              <div 
                className={`h-full ${accentColor.replace('border-', 'bg-')}`} 
                style={{ width: `${s.value}%` }}
              ></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default CharacterCard;
