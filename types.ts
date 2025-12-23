
export enum GameState {
  START = 'START',
  STORY = 'STORY',
  MINIGAME = 'MINIGAME',
  DESASTRE = 'DESASTRE',
  END = 'END'
}

export interface Choice {
  text: string;
  type: 'intellectual' | 'affectionate' | 'action';
  consequence?: string;
}

export interface StoryNode {
  chapter: string;
  title: string;
  date: string;
  text: string;
  choices: Choice[];
  imagePrompt?: string;
  bgImageUrl?: string;
}

export interface PlayerStats {
  connection: number;
  orderLevel: number; // For JM
  humorLevel: number; // For Vero
  booksSorted: number;
}

export interface MiniGameData {
  title: string;
  description: string;
  target: string;
  difficulty: number;
}
