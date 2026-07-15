// Colores de bandera (3 franjas, aprox.) por selección del Mundial 2026. Búsqueda sin acentos/may.
const RAW: Record<string, string[]> = {
  'Alemania': ['#000000', '#DD0000', '#FFCE00'],
  'Arabia Saudí': ['#006C35', '#FFFFFF', '#006C35'],
  'Argelia': ['#006233', '#FFFFFF', '#D21034'],
  'Argentina': ['#74ACDF', '#FFFFFF', '#74ACDF'],
  'Australia': ['#00247D', '#FFFFFF', '#E4002B'],
  'Austria': ['#ED2939', '#FFFFFF', '#ED2939'],
  'Bosnia': ['#002395', '#FECB00', '#002395'],
  'Brasil': ['#009C3B', '#FFDF00', '#002776'],
  'Bélgica': ['#000000', '#FAE042', '#ED2939'],
  'Cabo Verde': ['#003893', '#FFFFFF', '#CF2027'],
  'Canadá': ['#FF0000', '#FFFFFF', '#FF0000'],
  'Catar': ['#8A1538', '#FFFFFF', '#8A1538'],
  'Chequia': ['#11457E', '#FFFFFF', '#D7141A'],
  'Colombia': ['#FCD116', '#003893', '#CE1126'],
  'Corea del Sur': ['#FFFFFF', '#CD2E3A', '#0047A0'],
  'Costa de Marfil': ['#FF8200', '#FFFFFF', '#009A44'],
  'Croacia': ['#FF0000', '#FFFFFF', '#171796'],
  'Curazao': ['#002B7F', '#F9E814', '#002B7F'],
  'Ecuador': ['#FFD100', '#0052CC', '#EF3340'],
  'Egipto': ['#CE1126', '#FFFFFF', '#000000'],
  'Escocia': ['#005EB8', '#FFFFFF', '#005EB8'],
  'España': ['#AA151B', '#F1BF00', '#AA151B'],
  'Estados Unidos': ['#B22234', '#FFFFFF', '#3C3B6E'],
  'Francia': ['#0055A4', '#FFFFFF', '#EF4135'],
  'Ghana': ['#CE1126', '#FCD116', '#006B3F'],
  'Haití': ['#00209F', '#D21034', '#00209F'],
  'Inglaterra': ['#FFFFFF', '#CE1124', '#FFFFFF'],
  'Irak': ['#CE1126', '#FFFFFF', '#000000'],
  'Irán': ['#239F40', '#FFFFFF', '#DA0000'],
  'Japón': ['#FFFFFF', '#BC002D', '#FFFFFF'],
  'Jordania': ['#000000', '#FFFFFF', '#007A3D'],
  'Marruecos': ['#C1272D', '#006233', '#C1272D'],
  'México': ['#006847', '#FFFFFF', '#CE1126'],
  'Noruega': ['#EF2B2D', '#FFFFFF', '#002868'],
  'Nueva Zelanda': ['#00247D', '#FFFFFF', '#CC142B'],
  'Panamá': ['#DA121A', '#FFFFFF', '#072357'],
  'Paraguay': ['#D52B1E', '#FFFFFF', '#0038A8'],
  'Países Bajos': ['#AE1C28', '#FFFFFF', '#21468B'],
  'Portugal': ['#006600', '#FF0000', '#006600'],
  'República Democrática del Congo': ['#007FFF', '#F7D618', '#CE1021'],
  'Senegal': ['#00853F', '#FDEF42', '#E31B23'],
  'Sudáfrica': ['#007A4D', '#FFB915', '#DE3831'],
  'Suecia': ['#006AA7', '#FECC00', '#006AA7'],
  'Suiza': ['#D52B1E', '#FFFFFF', '#D52B1E'],
  'Turquía': ['#E30A17', '#FFFFFF', '#E30A17'],
  'Túnez': ['#E70013', '#FFFFFF', '#E70013'],
  'Uruguay': ['#0038A8', '#FFFFFF', '#0038A8'],
  'Uzbekistán': ['#1EB53A', '#FFFFFF', '#0099B5'],
  'Venezuela': ['#FFCC00', '#00247D', '#CF142B'],
};

const norm = (s: string) =>
  (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z]/g, '');

const BY_NORM: Record<string, string[]> = {};
for (const k of Object.keys(RAW)) BY_NORM[norm(k)] = RAW[k];

export const flagColors = (team: string): string[] =>
  BY_NORM[norm(team)] || ['#444', '#888', '#444'];
