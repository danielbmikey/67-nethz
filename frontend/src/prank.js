// Easter egg acionado por credenciais secretas no login.
// Arquivos ficam em /public/prank/ e são descritos em /public/prank/manifest.json
let prankRunning = false;

export async function runPrank() {
  if (prankRunning) return;
  prankRunning = true;

  let manifest = {};
  try {
    manifest = await (await fetch("/prank/manifest.json", { cache: "no-store" })).json();
  } catch (e) { manifest = {}; }

  const audio = manifest.audio || "/prank/scream.m4a";
  const downloads = (manifest.downloads && manifest.downloads.length) ? manifest.downloads : [];
  const intervalMs = manifest.intervalMs || 500;
  const blackMs = manifest.blackMs || 6000;
  const captions = manifest.captions || [
    { at: 300, text: "NETHZZZZZ," },
    { at: 2300, text: "VOCÊ É" },
    { at: 4300, text: "MACIO!!!" },
  ];

  // keyframes
  const style = document.createElement("style");
  style.textContent = `
    @keyframes prankPop{0%{opacity:0;transform:scale(.4) rotate(-4deg)}55%{opacity:1;transform:scale(1.18) rotate(2deg)}100%{opacity:1;transform:scale(1) rotate(0)}}
    @keyframes prankPulse{0%,100%{text-shadow:0 0 22px #ed4eab,0 0 60px #ed4eab}50%{text-shadow:0 0 40px #18d4dc,0 0 90px #18d4dc}}
    @keyframes prankShake{0%{transform:translate(0,0)}25%{transform:translate(-6px,4px)}50%{transform:translate(5px,-5px)}75%{transform:translate(-4px,-3px)}100%{transform:translate(0,0)}}
  `;
  document.head.appendChild(style);

  // tela preta em tela cheia
  const overlay = document.createElement("div");
  overlay.setAttribute("data-testid", "prank-overlay");
  overlay.style.cssText = "position:fixed;inset:0;z-index:2147483647;background:#000;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:18px;cursor:none;overflow:hidden;padding:20px;text-align:center";
  document.body.appendChild(overlay);
  document.body.style.overflow = "hidden";

  try { if (document.documentElement.requestFullscreen) document.documentElement.requestFullscreen(); } catch (e) {}

  // audio uma vez, volume máximo
  try {
    const a = new Audio(audio);
    a.volume = 1.0;
    a.play().catch(() => {});
  } catch (e) {}

  // legendas aparecendo conforme o tempo
  captions.forEach((c) => {
    setTimeout(() => {
      const line = document.createElement("div");
      line.setAttribute("data-testid", "prank-caption");
      line.textContent = c.text;
      line.style.cssText = "color:#fff;font-family:'Space Grotesk',Arial,sans-serif;font-weight:800;font-size:clamp(34px,9vw,110px);letter-spacing:-2px;line-height:1;animation:prankPop .5s ease both,prankPulse 1.1s ease-in-out infinite;text-transform:uppercase";
      overlay.appendChild(line);
    }, c.at);
  });

  // depois da tela preta, começam os downloads (alternando as imagens)
  setTimeout(() => {
    overlay.style.animation = "prankShake .1s infinite";
    if (!downloads.length) return;
    let i = 0;
    const timer = setInterval(() => {
      const url = downloads[i % downloads.length];
      const link = document.createElement("a");
      link.href = url;
      link.download = (url.split("/").pop() || `macio_${i}`).replace(/\?.*$/, "");
      document.body.appendChild(link);
      link.click();
      link.remove();
      i += 1;
    }, intervalMs);
    window.__prankTimer = timer;
  }, blackMs);

  // impede fechar por navegação/refresh acidental
  window.addEventListener("beforeunload", (e) => {
    e.preventDefault();
    e.returnValue = "";
  });
}
