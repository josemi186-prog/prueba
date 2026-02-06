import React from 'react';

const App: React.FC = () => {
  const featuredMatch = {
    tournament: 'Masters de Lisboa 2024',
    teams: ['Nova', 'Raven'],
    time: 'Hoy · 19:30 CET',
    bestOf: 'Bo3',
    mapPool: ['Mirage', 'Inferno', 'Nuke'],
    odds: '53% vs 47%',
    headline: 'Nova llega con 8 victorias seguidas y Raven estrena coach.'
  };

  const upcomingMatches = [
    {
      time: '16:00',
      event: 'Challenger Stage',
      teams: ['Lynx', 'Orbit'],
      format: 'Bo1',
      status: 'En 2h'
    },
    {
      time: '18:15',
      event: 'Liga Iberia',
      teams: ['Malaga Five', 'GranCan'],
      format: 'Bo3',
      status: 'En 4h'
    },
    {
      time: '20:45',
      event: 'Open Europa',
      teams: ['Aurora', 'Valkyrie'],
      format: 'Bo3',
      status: 'En 6h'
    },
    {
      time: '22:10',
      event: 'Pro Series',
      teams: ['Sombra', 'Tornado'],
      format: 'Bo1',
      status: 'En 8h'
    }
  ];

  const latestNews = [
    {
      title: 'Raven anuncia a Kiro como nuevo IGL tras la salida de Pola.',
      tag: 'Fichajes',
      time: 'Hace 23 min'
    },
    {
      title: 'Nova domina en Mirage y se mete en semifinales de Masters.',
      tag: 'Resultados',
      time: 'Hace 1 h'
    },
    {
      title: 'Guía del meta: por qué el doble AWP vuelve a estar de moda.',
      tag: 'Análisis',
      time: 'Hace 2 h'
    },
    {
      title: 'GranCan gana su primer título regional en Tenerife.',
      tag: 'Regiones',
      time: 'Hace 5 h'
    }
  ];

  const rankings = [
    { position: 1, team: 'Nova', points: 1000, trend: '+1' },
    { position: 2, team: 'Raven', points: 985, trend: '-1' },
    { position: 3, team: 'Aurora', points: 942, trend: '+2' },
    { position: 4, team: 'Valkyrie', points: 920, trend: '0' },
    { position: 5, team: 'Sombra', points: 901, trend: '+1' }
  ];

  const featuredVideos = [
    {
      title: 'Top 5 clutchs de la semana',
      duration: '6:42'
    },
    {
      title: 'Ruta táctica de Nuke para equipos semiprofesionales',
      duration: '10:18'
    },
    {
      title: 'Entrevista exclusiva con el coach de Nova',
      duration: '8:05'
    }
  ];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-amber-500 text-white font-extrabold">
              HL
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-slate-400">ArenaCS</p>
              <h1 className="text-lg font-semibold">El portal de Counter-Strike en español</h1>
            </div>
          </div>
          <nav className="flex flex-wrap items-center gap-4 text-sm font-semibold text-slate-600">
            <a className="hover:text-amber-600" href="#noticias">Noticias</a>
            <a className="hover:text-amber-600" href="#partidos">Partidos</a>
            <a className="hover:text-amber-600" href="#rankings">Rankings</a>
            <a className="hover:text-amber-600" href="#videos">Videos</a>
            <a className="hover:text-amber-600" href="#estadisticas">Estadísticas</a>
          </nav>
          <div className="flex items-center gap-2">
            <button className="rounded-full border border-slate-300 px-4 py-2 text-xs font-semibold text-slate-700 hover:border-amber-400 hover:text-amber-600">
              Entrar
            </button>
            <button className="rounded-full bg-amber-500 px-4 py-2 text-xs font-semibold text-white">
              Seguir torneo
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-6xl gap-8 px-4 pb-16 pt-8 lg:grid-cols-[2.1fr_1fr]">
        <section className="space-y-8">
          <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-6">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-amber-600">Partido destacado</p>
                <h2 className="mt-2 text-3xl font-bold">{featuredMatch.teams[0]} vs {featuredMatch.teams[1]}</h2>
                <p className="mt-2 text-sm text-slate-500">{featuredMatch.tournament} · {featuredMatch.time}</p>
              </div>
              <div className="rounded-2xl border border-amber-200 bg-amber-50 px-6 py-4 text-sm text-amber-700">
                <p className="font-semibold">{featuredMatch.bestOf}</p>
                <p className="mt-2">{featuredMatch.odds}</p>
              </div>
            </div>
            <p className="mt-6 text-lg text-slate-700">{featuredMatch.headline}</p>
            <div className="mt-6 flex flex-wrap gap-3 text-xs font-semibold uppercase">
              {featuredMatch.mapPool.map((map) => (
                <span key={map} className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-slate-600">
                  {map}
                </span>
              ))}
            </div>
            <div className="mt-8 flex flex-wrap gap-4">
              <button className="rounded-full bg-amber-500 px-6 py-3 text-sm font-semibold text-white">
                Ver previa
              </button>
              <button className="rounded-full border border-slate-300 px-6 py-3 text-sm font-semibold text-slate-700">
                Añadir al calendario
              </button>
            </div>
          </div>

          <section id="noticias" className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-xl font-semibold">Últimas noticias</h3>
              <button className="text-xs font-semibold text-amber-600">Ver todo</button>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              {latestNews.map((item) => (
                <article key={item.title} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="flex items-center justify-between text-xs text-slate-500">
                    <span className="rounded-full bg-amber-50 px-3 py-1 text-amber-700">{item.tag}</span>
                    <span>{item.time}</span>
                  </div>
                  <h4 className="mt-3 text-lg font-semibold text-slate-900">{item.title}</h4>
                </article>
              ))}
            </div>
          </section>

          <section id="partidos" className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-xl font-semibold">Partidos en directo</h3>
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-600">4 próximos</span>
            </div>
            <div className="space-y-3">
              {upcomingMatches.map((match) => (
                <div key={`${match.time}-${match.event}`} className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div>
                    <p className="text-sm text-slate-500">{match.time} · {match.event}</p>
                    <p className="mt-1 text-lg font-semibold">{match.teams[0]} <span className="text-slate-400">vs</span> {match.teams[1]}</p>
                  </div>
                  <div className="flex items-center gap-3 text-sm">
                    <span className="rounded-full border border-slate-200 px-3 py-1 text-slate-600">{match.format}</span>
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-500">{match.status}</span>
                    <button className="rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white">Ver</button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </section>

        <aside className="space-y-6">
          <section id="rankings" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">Ranking mundial</h3>
              <span className="text-xs text-slate-400">Actualizado hoy</span>
            </div>
            <div className="mt-4 space-y-3">
              {rankings.map((team) => (
                <div key={team.team} className="flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50 px-4 py-3">
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-semibold text-amber-600">#{team.position}</span>
                    <div>
                      <p className="text-sm font-semibold">{team.team}</p>
                      <p className="text-xs text-slate-500">{team.points} pts</p>
                    </div>
                  </div>
                  <span className="text-xs font-semibold text-emerald-600">{team.trend}</span>
                </div>
              ))}
            </div>
            <button className="mt-4 w-full rounded-xl border border-slate-300 px-4 py-2 text-xs font-semibold text-slate-700">
              Ver ranking completo
            </button>
          </section>

          <section id="videos" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="text-lg font-semibold">Videos recomendados</h3>
            <div className="mt-4 space-y-4">
              {featuredVideos.map((video) => (
                <div key={video.title} className="flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50 px-4 py-3">
                  <div>
                    <p className="text-sm font-semibold">{video.title}</p>
                    <p className="text-xs text-slate-500">{video.duration}</p>
                  </div>
                  <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700">Play</span>
                </div>
              ))}
            </div>
          </section>

          <section id="estadisticas" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="text-lg font-semibold">Panel de estadísticas</h3>
            <div className="mt-4 space-y-3 text-sm text-slate-600">
              <div className="flex items-start gap-3">
                <span className="mt-1 h-2 w-2 rounded-full bg-amber-500"></span>
                <p>Raven juega con nuevo rifler: atención a las bajas tempranas.</p>
              </div>
              <div className="flex items-start gap-3">
                <span className="mt-1 h-2 w-2 rounded-full bg-emerald-500"></span>
                <p>Nova mantiene un 78% de winrate en Inferno esta temporada.</p>
              </div>
              <div className="flex items-start gap-3">
                <span className="mt-1 h-2 w-2 rounded-full bg-sky-500"></span>
                <p>Se abre el clasificatorio para la Liga Iberia 2025.</p>
              </div>
            </div>
          </section>
        </aside>
      </main>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 py-8 text-xs text-slate-500 sm:flex-row">
          <p>© 2024 ArenaCS. Inspirado en las mejores coberturas de esports.</p>
          <div className="flex gap-4">
            <a className="hover:text-amber-600" href="#">Política</a>
            <a className="hover:text-amber-600" href="#">Contacto</a>
            <a className="hover:text-amber-600" href="#">Newsletter</a>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;
