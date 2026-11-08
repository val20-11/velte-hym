// dibujos de las prendas para cuando no hay foto del producto
const COLORES = {
  negro: "#3b3b3d", gris: "#a9adb3", blanco: "#f7f7f5", beige: "#dcc9ad", cafe: "#8a6446",
  rosa: "#eab3c0", rojo: "#c8323c", azul: "#5a7fb5", verde: "#6f8f6a", amarillo: "#e8c45a",
};

const FIGURAS = {
  chamarra: `
    <path d="M42 20 L52 16 Q60 24 68 16 L78 20 L96 32 L104 84 L91 86 L87 52 L87 102 L33 102 L33 52 L29 86 L16 84 L24 32 Z"/>
    <path d="M52 16 L58 32 L60 102 M68 16 L62 32" fill="none"/>
    <path d="M40 72 h12 M68 72 h12 M40 60 h12 M68 60 h12" fill="none"/>
    <circle cx="66" cy="46" r="1.6"/><circle cx="66" cy="62" r="1.6"/><circle cx="66" cy="78" r="1.6"/>`,
  blazer: `
    <path d="M42 20 L52 16 Q60 22 68 16 L78 20 L96 32 L104 86 L91 88 L87 52 L87 102 L33 102 L33 52 L29 88 L16 86 L24 32 Z"/>
    <path d="M52 16 L55 50 L60 62 L65 50 L68 16 M60 62 L60 102" fill="none"/>
    <circle cx="60" cy="74" r="2"/><circle cx="60" cy="86" r="2"/>
    <path d="M40 80 h12 M72 46 h9" fill="none"/>`,
  sudadera: `
    <path d="M44 26 Q60 4 76 26 L92 32 L102 82 L90 84 L86 52 L86 102 L34 102 L34 52 L30 84 L18 82 L28 32 Z"/>
    <path d="M44 26 Q60 38 76 26" fill="none"/>
    <path d="M56 32 v12 M64 32 v12" fill="none"/>
    <path d="M44 74 L76 74 L72 92 L48 92 Z" fill="none"/>
    <path d="M34 96 h52" fill="none"/>`,
  blusa: `
    <path d="M44 20 Q60 34 76 20 L96 30 L91 52 L82 48 L84 102 L36 102 L38 48 L29 52 L24 30 Z"/>
    <path d="M44 20 Q60 34 76 20" fill="none"/>
    <path d="M52 30 Q56 38 60 30 Q64 38 68 30" fill="none"/>
    <path d="M38 62 Q60 68 82 62" fill="none"/>`,
  vestido: `
    <path d="M47 12 L50 12 Q60 24 70 12 L73 12 L72 46 L98 106 L22 106 L48 46 Z"/>
    <path d="M48 46 Q60 50 72 46" fill="none"/>
    <path d="M52 52 L44 104 M60 52 L60 106 M68 52 L76 104" fill="none" opacity=".45"/>`,
  tenis: `
    <path d="M14 80 L18 54 Q30 54 40 46 L52 40 Q60 54 76 58 L98 64 Q108 68 106 80 Z"/>
    <path d="M12 80 L108 80 L106 92 L14 92 Z"/>
    <path d="M46 50 l8 6 M52 46 l8 6 M40 54 l8 6" fill="none"/>
    <path d="M20 86 h80" fill="none" opacity=".5"/>`,
  botas: `
    <path d="M40 14 L72 14 L72 64 Q94 68 100 82 L100 96 L40 96 Z"/>
    <path d="M38 96 L102 96 L102 106 L38 106 Z"/>
    <path d="M40 30 h32 M58 14 v50" fill="none"/>`,
  bolsa: `
    <path d="M42 44 Q42 16 60 16 Q78 16 78 44" fill="none" stroke-width="3"/>
    <path d="M22 44 L98 44 L104 104 L16 104 Z"/>
    <path d="M22 44 L60 64 L98 44" fill="none"/>
    <rect x="55" y="60" width="10" height="9" rx="2"/>`,
};

function dibujoPrenda(tipo, color) {
  const relleno = COLORES[(color || "").toLowerCase()] || "#cfc6bb";
  const oscuro = ["negro", "cafe", "azul", "rojo", "verde"].includes((color || "").toLowerCase());
  const trazo = oscuro ? "#1b1b1b" : "#2c2c2c";
  return `<svg viewBox="0 0 120 120" class="prenda-svg" fill="${relleno}" stroke="${trazo}"
            stroke-width="2" stroke-linejoin="round" stroke-linecap="round">${FIGURAS[tipo] || FIGURAS.blusa}</svg>`;
}
