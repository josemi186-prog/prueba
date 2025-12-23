
import { GoogleGenAI, Type } from "@google/genai";
import { StoryNode, PlayerStats } from "./types";

const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });

const SYSTEM_INSTRUCTION = `Actúa como un motor de juego de aventura narrativa e interactiva titulado "Agapea: El Catálogo del Destino". 
Personajes:
- José Miguel (JM): Malagueño, 1.88m, piel muy blanca, barba, fan del orden (esquemas/tablas). Historiador.
- Verónica (Vero): Canaria, 1.60m, morena, pelazo rizado, gran sentido del humor. Historiadora.
Intereses: Egipto, Roma, Lost, Regreso al Futuro, Severance, Pata asada, Sushi, Campero malagueño.

Mecánicas:
1. Divide por capítulos: Agapea (2022), Despedida (28 Abril 2023), Beso Casa María (Sept 2023), Casa Budaperro (Oct 2023), Mudanza (Marzo 2024).
2. Tono: Ingenioso, histórico, sci-fi. Usa términos canarios: fleje, pelete, gofio, ñanga, emboste.
3. El sistema de "Desastres": Cada escena importante debe incluir un componente de caos (tráfico, olvidos) que une a los personajes.
4. Genera opciones de diálogo: Una intelectual/académica y otra cariñosa/humorística.

Responde SIEMPRE en formato JSON siguiendo el esquema StoryNode definido.`;

export async function getNextStoryNode(
  currentChapter: string,
  lastChoice: string,
  stats: PlayerStats
): Promise<StoryNode> {
  const prompt = `
    Contexto actual: Capítulo ${currentChapter}.
    Última decisión del jugador: "${lastChoice}".
    Estadísticas actuales: Conexión=${stats.connection}, Orden=${stats.orderLevel}, Humor=${stats.humorLevel}.
    
    Genera el siguiente fragmento de la historia de JM y Vero. 
    Si estamos en el Capítulo 1, sitúalos en Agapea Las Palmas, calle Franchy Roca.
    Asegúrate de incluir referencias a sus personalidades de historiadores.
  `;

  const response = await ai.models.generateContent({
    model: "gemini-3-flash-preview",
    contents: prompt,
    config: {
      systemInstruction: SYSTEM_INSTRUCTION,
      responseMimeType: "application/json",
      responseSchema: {
        type: Type.OBJECT,
        properties: {
          chapter: { type: Type.STRING },
          title: { type: Type.STRING },
          date: { type: Type.STRING },
          text: { type: Type.STRING },
          choices: {
            type: Type.ARRAY,
            items: {
              type: Type.OBJECT,
              properties: {
                text: { type: Type.STRING },
                type: { type: Type.STRING, enum: ['intellectual', 'affectionate', 'action'] },
                consequence: { type: Type.STRING }
              },
              required: ["text", "type"]
            }
          },
          bgImageUrl: { type: Type.STRING }
        },
        required: ["chapter", "title", "date", "text", "choices"]
      },
    },
  });

  return JSON.parse(response.text);
}
