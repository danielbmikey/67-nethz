from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
import asyncio, csv, io, logging, os, random, re, uuid, bcrypt, jwt
import resend
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field

load_dotenv(Path(__file__).parent / ".env")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ["JWT_SECRET"]
ADMIN_EMAIL = os.environ["ADMIN_EMAIL"].lower()
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
ADMIN2_USERNAME = os.environ.get("ADMIN2_USERNAME", "").lower().strip()
ADMIN2_PASSWORD = os.environ.get("ADMIN2_PASSWORD", "")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
if RESEND_API_KEY: resend.api_key = RESEND_API_KEY
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]
now = lambda: datetime.now(timezone.utc).isoformat()
NICK_RE = re.compile(r"^[A-Za-z0-9_.-]{3,24}$")
DEFAULT_SETTINGS = {
    "hero_eyebrow": "TRANSMISSÃO EM BREVE • QUARTA 20:00",
    "hero_title1": "A Tropa",
    "hero_title2": "Decide.",
    "hero_paragraph": "O quartel-general da comunidade do Neth. Sugira o próximo jogo, compartilhe aquele clipe absurdo e faça a live acontecer.",
    "next_live": "QUARTA, 20:00",
    "twitch_url": "https://twitch.tv/nethzzzzz",
    "youtube_url": "https://youtube.com",
    "instagram_url": "https://instagram.com",
    "footer_status": "COMUNIDADE ONLINE",
}

def uid(): return str(uuid.uuid4())
def strip_id(doc): return {k: v for k, v in doc.items() if k != "_id"} if doc else None
def ts(): return datetime.now(timezone.utc).timestamp()
def token_for(sub, role, days=1): return jwt.encode({"sub": sub, "role": role, "exp": ts() + days * 86400}, JWT_SECRET, algorithm="HS256")
def hash_pw(pw): return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
def check_pw(pw, hashed): return bcrypt.checkpw(pw.encode(), hashed.encode())
def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd: return fwd.split(",")[0].strip()
    real = request.headers.get("x-real-ip")
    return real or (request.client.host if request.client else "0.0.0.0")

# ---------- Email (Resend) ----------
async def send_email(to, subject, html):
    if not RESEND_API_KEY:
        logging.warning("RESEND_API_KEY ausente; email nao enviado para %s", to)
        return False
    try:
        await asyncio.to_thread(resend.Emails.send, {"from": f"NETHZZZZ HQ <{SENDER_EMAIL}>", "to": [to], "subject": subject, "html": html})
        return True
    except Exception as exc:
        logging.error("Falha ao enviar email para %s: %s", to, exc)
        return False

def code_email_html(title, message, code):
    return f"""<div style="background:#0b0c10;color:#e8e9ef;padding:36px;font-family:Arial,sans-serif">
      <h2 style="color:#ed4eab;letter-spacing:2px;margin:0 0 4px">NETHZZZZ HQ</h2>
      <p style="color:#8b8fa3;font-size:11px;letter-spacing:2px;margin:0 0 24px">CUIUDOS DELICIOSOS FAN CLUB</p>
      <h3 style="margin:0 0 12px">{title}</h3>
      <p style="color:#b8bcd0;line-height:1.6">{message}</p>
      <div style="background:#15171f;border:1px solid #ed4eab;padding:18px;text-align:center;font-size:30px;letter-spacing:10px;color:#18d4dc;font-weight:bold;margin:22px 0">{code}</div>
      <p style="color:#8b8fa3;font-size:12px">O c&oacute;digo expira em 30 minutos. Se voc&ecirc; n&atilde;o solicitou, ignore este email.</p>
    </div>"""

async def issue_code(email, purpose):
    code = f"{random.randint(0, 999999):06d}"
    await db.email_codes.update_one({"email": email, "purpose": purpose}, {"$set": {"code": code, "expires_at": ts() + 1800, "issued_ts": ts(), "used": False}}, upsert=True)
    return code

async def consume_code(email, purpose, code):
    doc = await db.email_codes.find_one({"email": email, "purpose": purpose, "used": False})
    if not doc or doc["code"] != code.strip() or doc["expires_at"] < ts(): return False
    await db.email_codes.update_one({"_id": doc["_id"]}, {"$set": {"used": True}})
    return True

# ---------- Brute-force lockout ----------
LOCK_MAX_FAILS, LOCK_WINDOW = 5, 900

async def check_lock(email):
    doc = await db.login_attempts.find_one({"email": email})
    if doc and doc.get("locked_until", 0) > ts():
        mins = int((doc["locked_until"] - ts()) // 60) + 1
        raise HTTPException(423, f"Muitas tentativas erradas. Tente novamente em {mins} min.")

async def register_fail(email):
    doc = await db.login_attempts.find_one({"email": email})
    fails = (doc.get("fails", 0) + 1) if doc else 1
    update = {"fails": fails, "last_fail": ts()}
    if fails >= LOCK_MAX_FAILS:
        update.update({"fails": 0, "locked_until": ts() + LOCK_WINDOW})
    await db.login_attempts.update_one({"email": email}, {"$set": update}, upsert=True)

async def clear_fails(email):
    await db.login_attempts.delete_one({"email": email})

async def decode_token(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        header = request.headers.get("Authorization", "")
        token = header[7:] if header.startswith("Bearer ") else None
    if not token: return None
    try: return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError: return None

async def admin_only(request: Request):
    payload = await decode_token(request)
    if not payload: raise HTTPException(401, "Faça login para acessar o painel.")
    if payload.get("role") != "admin": raise HTTPException(403, "Acesso restrito à administração.")
    admin = await db.admins.find_one({"id": payload.get("sub")})
    if not admin: raise HTTPException(403, "Sessão de admin inválida.")
    return admin

async def current_user(request: Request):
    payload = await decode_token(request)
    if not payload: return None
    if payload.get("role") == "admin":
        admin = await db.admins.find_one({"id": payload.get("sub")}, {"_id": 0, "password_hash": 0})
        if not admin: return None
        return {"id": admin["id"], "nickname": admin.get("name", "STREAMER"), "email": admin.get("email") or admin.get("username"), "role": "admin", "is_verified": True}
    user = await db.users.find_one({"id": payload.get("sub")}, {"_id": 0, "password_hash": 0})
    return user

async def require_user(request: Request):
    user = await current_user(request)
    if not user: raise HTTPException(401, "Faça login ou crie sua conta na tropa.")
    return user

class GameCreate(BaseModel): title: str; genre: str; description: str; platform: str = "PC"
class ClipCreate(BaseModel): title: str; url: str; clip_type: str = "link"
class CommentCreate(BaseModel): target_id: str; target_type: str; content: str
class ReportCreate(BaseModel): target_id: str; target_type: str; reason: str
class PollCreate(BaseModel): question: str; options: List[str]
class ScheduleCreate(BaseModel): day: str; time: str; game: str; description: str = ""; is_special: bool = False
class SiteSettings(BaseModel):
    hero_eyebrow: str; hero_title1: str; hero_title2: str; hero_paragraph: str
    next_live: str; twitch_url: str; youtube_url: str; instagram_url: str; footer_status: str
class Login(BaseModel): email: str; password: str; remember: bool = False
class Signup(BaseModel): email: EmailStr; password: str = Field(min_length=6, max_length=72); nickname: str
class VerifyCode(BaseModel): code: str
class ForgotPassword(BaseModel): email: EmailStr
class ResetPassword(BaseModel): email: EmailStr; code: str; new_password: str = Field(min_length=6, max_length=72)

@asynccontextmanager
async def lifespan(app):
    try:
        await db.admins.create_index("id", unique=True)
        await db.users.create_index("email", unique=True)
        await db.users.create_index("nickname", unique=True)
        await db.login_attempts.create_index("email")
        await db.email_codes.create_index("expires_at", expireAfterSeconds=0)
        # Admin 1 (email)
        a1 = await db.admins.find_one({"email": ADMIN_EMAIL})
        if not a1:
            await db.admins.insert_one({"id": uid(), "email": ADMIN_EMAIL, "username": None, "name": "STREAMER", "password_hash": hash_pw(ADMIN_PASSWORD), "role": "admin"})
        elif not check_pw(ADMIN_PASSWORD, a1["password_hash"]):
            await db.admins.update_one({"email": ADMIN_EMAIL}, {"$set": {"password_hash": hash_pw(ADMIN_PASSWORD)}})
        # Admin 2 (username) — super admin do Neth
        if ADMIN2_USERNAME and ADMIN2_PASSWORD:
            a2 = await db.admins.find_one({"username": ADMIN2_USERNAME})
            if not a2:
                await db.admins.insert_one({"id": uid(), "email": None, "username": ADMIN2_USERNAME, "name": "NETHZ", "password_hash": hash_pw(ADMIN2_PASSWORD), "role": "admin"})
            elif not check_pw(ADMIN2_PASSWORD, a2["password_hash"]):
                await db.admins.update_one({"username": ADMIN2_USERNAME}, {"$set": {"password_hash": hash_pw(ADMIN2_PASSWORD)}})
        if await db.settings.count_documents({}) == 0:
            await db.settings.insert_one({"_key": "site", **DEFAULT_SETTINGS})
        if await db.schedule.count_documents({}) == 0:
            await db.schedule.insert_many([
                {"id":uid(),"day":"Segunda-feira","time":"19:00 BRT","game":"Valorant & Ranqueadas","description":"Subindo pro Imortal com o chat","is_special":False},
                {"id":uid(),"day":"Quarta-feira","time":"20:00 BRT","game":"Jogos Sugeridos pelo Chat","description":"Testando as melhores sugestões da comunidade!","is_special":True},
                {"id":uid(),"day":"Sexta-feira","time":"21:00 BRT","game":"Terror & Sustos","description":"Noite de cagaço coletivo","is_special":False},
            ])
        if await db.polls.count_documents({}) == 0:
            await db.polls.insert_one({"id":uid(),"question":"Qual jogo o Neth deve zerar na maratona de 12 horas?","options":[{"text":"Dark Souls 3 sem tomar hit","votes":0},{"text":"Outlast Trials Hardcore","votes":0},{"text":"GTA San Andreas Chaos Mod","votes":0}],"is_active":True,"created_at":now()})
    except Exception as exc:
        logging.error("Seed warning: %s", exc)
    yield
    client.close()

app = FastAPI(title="Nethzzzz Community HQ", lifespan=lifespan)
api = APIRouter(prefix="/api")

async def many(collection): return await db[collection].find({}, {"_id": 0}).to_list(1000)

# ---------- Public reads ----------
@api.get("/")
async def root(): return {"message": "API do @nethzzzz operando"}

@api.get("/games")
async def games(): return await many("games")

@api.get("/clips")
async def clips(): return await many("clips")

@api.get("/comments/{target_id}")
async def comments(target_id: str): return await db.comments.find({"target_id": target_id}, {"_id": 0}).sort("created_at", 1).to_list(1000)

@api.get("/polls")
async def polls(): return await many("polls")

@api.get("/schedule")
async def schedule(): return await many("schedule")

@api.get("/settings")
async def get_settings():
    doc = await db.settings.find_one({"_key": "site"}, {"_id": 0, "_key": 0})
    return doc or DEFAULT_SETTINGS

# ---------- Admin: live site editing ----------
@api.put("/admin/settings")
async def update_settings(item: SiteSettings, _: dict = Depends(admin_only)):
    await db.settings.update_one({"_key": "site"}, {"$set": item.model_dump()}, upsert=True)
    doc = await db.settings.find_one({"_key": "site"}, {"_id": 0, "_key": 0})
    return doc

@api.post("/admin/schedule")
async def add_schedule(item: ScheduleCreate, _: dict = Depends(admin_only)):
    doc = {"id": uid(), **item.model_dump()}
    await db.schedule.insert_one(doc)
    return strip_id(doc)

@api.delete("/admin/schedule/{item_id}")
async def delete_schedule(item_id: str, _: dict = Depends(admin_only)):
    await db.schedule.delete_one({"id": item_id})
    return {"success": True}

@api.post("/admin/polls")
async def add_poll(item: PollCreate, _: dict = Depends(admin_only)):
    opts = [o.strip() for o in item.options if o.strip()]
    if len(opts) < 2: raise HTTPException(400, "A enquete precisa de pelo menos 2 opções.")
    doc = {"id": uid(), "question": item.question.strip(), "options": [{"text": o, "votes": 0} for o in opts], "is_active": True, "created_at": now()}
    await db.polls.insert_one(doc)
    return strip_id(doc)

@api.delete("/admin/polls/{poll_id}")
async def delete_poll(poll_id: str, _: dict = Depends(admin_only)):
    await db.polls.delete_one({"id": poll_id})
    return {"success": True}

@api.get("/stats")
async def stats():
    return {
        "members": await db.users.count_documents({}),
        "games": await db.games.count_documents({}),
        "clips": await db.clips.count_documents({}),
    }

async def _counts_by(collection, field):
    rows = await db[collection].aggregate([{"$group": {"_id": f"${field}", "n": {"$sum": 1}}}]).to_list(10000)
    return {r["_id"]: r["n"] for r in rows if r["_id"]}

@api.get("/ranking")
async def ranking():
    games_c = await _counts_by("games", "submitted_by_id")
    clips_c = await _counts_by("clips", "submitted_by_id")
    comments_c = await _counts_by("comments", "author_id")
    votes_c = await _counts_by("votes", "user_id")
    users = await db.users.find({}, {"_id": 0, "id": 1, "nickname": 1, "is_verified": 1}).to_list(5000)
    board = []
    for u in users:
        g, c, m, v = games_c.get(u["id"], 0), clips_c.get(u["id"], 0), comments_c.get(u["id"], 0), votes_c.get(u["id"], 0)
        score = g * 3 + c * 3 + m * 2 + v
        if score > 0:
            board.append({"nickname": u["nickname"], "is_verified": u.get("is_verified", False), "score": score, "games": g, "clips": c, "comments": m, "votes": v})
    board.sort(key=lambda x: x["score"], reverse=True)
    return board[:10]

@api.get("/users/{nickname}/profile")
async def user_profile(nickname: str):
    user = await db.users.find_one({"nickname": nickname}, {"_id": 0, "password_hash": 0, "email": 0, "creation_ip": 0, "last_ip": 0})
    if not user: raise HTTPException(404, "Membro não encontrado.")
    games = await db.games.find({"submitted_by_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    clips = await db.clips.find({"submitted_by_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    comments_n = await db.comments.count_documents({"author_id": user["id"]})
    votes_n = await db.votes.count_documents({"user_id": user["id"]})
    badges = []
    if user.get("is_verified"): badges.append({"id": "verified", "label": "Verificado", "desc": "Email confirmado no QG"})
    if len(games) >= 1: badges.append({"id": "strategist", "label": "Estrategista", "desc": "Sugeriu um jogo pra tropa"})
    if len(games) >= 5: badges.append({"id": "curator", "label": "Curador da Arena", "desc": "5+ jogos sugeridos"})
    if len(clips) >= 1: badges.append({"id": "director", "label": "Cinegrafista", "desc": "Enviou um clipe pro hub"})
    if any(c.get("likes", 0) >= 10 for c in clips): badges.append({"id": "legend", "label": "Clipe Lendário", "desc": "Um clipe com 10+ curtidas"})
    if comments_n >= 10: badges.append({"id": "voice", "label": "Voz Ativa", "desc": "10+ comentários na arena"})
    if votes_n >= 10: badges.append({"id": "elector", "label": "Eleitor de Elite", "desc": "10+ votos registrados"})
    return {
        "nickname": user["nickname"], "is_verified": user.get("is_verified", False), "created_at": user["created_at"],
        "games": games, "clips": clips,
        "stats": {"games": len(games), "clips": len(clips), "comments": comments_n, "votes": votes_n},
        "badges": badges,
    }

# ---------- Auth ----------
@api.post("/auth/signup")
async def signup(item: Signup, request: Request, response: Response):
    email = item.email.lower().strip()
    nickname = item.nickname.strip()
    if not NICK_RE.match(nickname): raise HTTPException(400, "Nickname inválido. Use 3-24 caracteres (letras, números, _ . -).")
    if await db.users.find_one({"email": email}): raise HTTPException(409, "Este email já está na tropa.")
    if await db.users.find_one({"nickname": nickname}): raise HTTPException(409, "Nickname já está em uso.")
    ip = client_ip(request)
    user = {
        "id": uid(),
        "email": email,
        "nickname": nickname,
        "password_hash": hash_pw(item.password),
        "role": "viewer",
        "is_verified": False,
        "creation_ip": ip,
        "last_ip": ip,
        "created_at": now(),
        "last_login": now(),
    }
    await db.users.insert_one(user)
    code = await issue_code(email, "verify")
    sent = await send_email(email, "Confirme seu email — NETHZZZZ HQ", code_email_html("Bem-vindo à tropa!", f"E aí, <b>{nickname}</b>! Use o código abaixo pra verificar sua conta no quartel-general.", code))
    token = token_for(user["id"], "viewer")
    response.set_cookie("access_token", token, httponly=True, secure=True, samesite="none", max_age=86400)
    return {"id": user["id"], "email": email, "nickname": nickname, "role": "viewer", "is_verified": False, "verification_sent": sent, "token": token}

@api.post("/auth/login")
async def login(item: Login, request: Request, response: Response):
    identifier = item.email.lower().strip()
    await check_lock(identifier)
    ip = client_ip(request)
    days = 30 if item.remember else 1
    admin = await db.admins.find_one({"$or": [{"email": identifier}, {"username": identifier}]})
    if admin and check_pw(item.password, admin["password_hash"]):
        await clear_fails(identifier)
        token = token_for(admin["id"], "admin", days)
        response.set_cookie("access_token", token, httponly=True, secure=True, samesite="none", max_age=days * 86400)
        return {"id": admin["id"], "email": admin.get("email") or admin.get("username"), "nickname": admin.get("name", "STREAMER"), "role": "admin", "is_verified": True, "token": token}
    user = await db.users.find_one({"email": identifier})
    if not user or not check_pw(item.password, user["password_hash"]):
        await register_fail(identifier)
        raise HTTPException(401, "Credenciais incorretas.")
    await clear_fails(identifier)
    await db.users.update_one({"id": user["id"]}, {"$set": {"last_ip": ip, "last_login": now()}})
    token = token_for(user["id"], "viewer", days)
    response.set_cookie("access_token", token, httponly=True, secure=True, samesite="none", max_age=days * 86400)
    return {"id": user["id"], "email": user["email"], "nickname": user["nickname"], "role": "viewer", "is_verified": user.get("is_verified", False), "token": token}

@api.get("/auth/me")
async def me(user=Depends(require_user)): return user

@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"success": True}

@api.post("/auth/verify")
async def verify_email(item: VerifyCode, user=Depends(require_user)):
    if user.get("role") == "admin" or user.get("is_verified"): return {"is_verified": True}
    if not await consume_code(user["email"], "verify", item.code): raise HTTPException(400, "Código inválido ou expirado.")
    await db.users.update_one({"id": user["id"]}, {"$set": {"is_verified": True}})
    return {"is_verified": True}

@api.post("/auth/resend-verification")
async def resend_verification(user=Depends(require_user)):
    if user.get("role") == "admin" or user.get("is_verified"): raise HTTPException(400, "Conta já verificada.")
    doc = await db.email_codes.find_one({"email": user["email"], "purpose": "verify"})
    if doc and ts() - doc.get("issued_ts", 0) < 60: raise HTTPException(429, "Aguarde 1 minuto para reenviar.")
    code = await issue_code(user["email"], "verify")
    sent = await send_email(user["email"], "Confirme seu email — NETHZZZZ HQ", code_email_html("Verificação de conta", f"E aí, <b>{user['nickname']}</b>! Aqui está seu novo código de verificação.", code))
    if not sent: raise HTTPException(502, "Não foi possível enviar o email agora. Tente novamente.")
    return {"sent": True}

@api.post("/auth/forgot-password")
async def forgot_password(item: ForgotPassword):
    email = item.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if user:
        doc = await db.email_codes.find_one({"email": email, "purpose": "reset"})
        if doc and ts() - doc.get("issued_ts", 0) < 60: raise HTTPException(429, "Aguarde 1 minuto para pedir outro código.")
        code = await issue_code(email, "reset")
        await send_email(email, "Recuperação de senha — NETHZZZZ HQ", code_email_html("Recuperação de senha", f"Olá, <b>{user['nickname']}</b>! Use o código abaixo pra criar uma nova senha.", code))
    return {"message": "Se o email estiver cadastrado, enviamos um código de recuperação."}

@api.post("/auth/reset-password")
async def reset_password(item: ResetPassword):
    email = item.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not await consume_code(email, "reset", item.code): raise HTTPException(400, "Código inválido ou expirado.")
    await db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": hash_pw(item.new_password)}})
    await clear_fails(email)
    return {"message": "Senha alterada! Faça login com a nova senha."}

# ---------- Suggestions ----------
@api.post("/games")
async def create_game(item: GameCreate, user=Depends(require_user)):
    doc = {"id": uid(), **item.model_dump(), "submitted_by": user["nickname"], "submitted_by_id": user["id"], "votes": 0, "status": "Pendente", "marked_as_played": False, "created_at": now()}
    await db.games.insert_one(doc)
    return strip_id(doc)

@api.post("/games/{item_id}/vote")
async def vote_game(item_id: str, request: Request, user=Depends(require_user)):
    key = f"game:{item_id}:{user['id']}"
    existing = await db.votes.find_one({"key": key})
    if existing: raise HTTPException(400, "Você já votou nessa sugestão.")
    await db.votes.insert_one({"key": key, "user_id": user["id"], "target_id": item_id, "created_at": now()})
    await db.games.update_one({"id": item_id}, {"$inc": {"votes": 1}})
    item = await db.games.find_one({"id": item_id}, {"_id": 0})
    if not item: raise HTTPException(404, "Jogo não encontrado.")
    return item

@api.patch("/games/{item_id}/status")
async def status_game(item_id: str, status: str, marked_as_played: Optional[bool] = None, _: dict = Depends(admin_only)):
    update = {"status": status}
    if marked_as_played is not None: update["marked_as_played"] = marked_as_played
    await db.games.update_one({"id": item_id}, {"$set": update})
    return await db.games.find_one({"id": item_id}, {"_id": 0})

@api.delete("/games/{item_id}")
async def delete_game(item_id: str, _: dict = Depends(admin_only)):
    await db.games.delete_one({"id": item_id})
    return {"success": True}

# ---------- Clips ----------
@api.post("/clips")
async def create_clip(item: ClipCreate, user=Depends(require_user)):
    doc = {"id": uid(), **item.model_dump(), "submitted_by": user["nickname"], "submitted_by_id": user["id"], "likes": 0, "created_at": now()}
    await db.clips.insert_one(doc)
    return strip_id(doc)

@api.post("/clips/{item_id}/like")
async def like_clip(item_id: str, user=Depends(require_user)):
    key = f"clip:{item_id}:{user['id']}"
    existing = await db.votes.find_one({"key": key})
    if existing: raise HTTPException(400, "Você já curtiu esse clipe.")
    await db.votes.insert_one({"key": key, "user_id": user["id"], "target_id": item_id, "created_at": now()})
    await db.clips.update_one({"id": item_id}, {"$inc": {"likes": 1}})
    return await db.clips.find_one({"id": item_id}, {"_id": 0})

@api.delete("/clips/{item_id}")
async def delete_clip(item_id: str, _: dict = Depends(admin_only)):
    await db.clips.delete_one({"id": item_id})
    return {"success": True}

# ---------- Comments ----------
@api.post("/comments")
async def create_comment(item: CommentCreate, user=Depends(require_user)):
    content = item.content.strip()
    if not content or len(content) > 500: raise HTTPException(400, "Comentário inválido (1-500 caracteres).")
    doc = {"id": uid(), "target_id": item.target_id, "target_type": item.target_type, "author": user["nickname"], "author_id": user["id"], "content": content, "created_at": now()}
    await db.comments.insert_one(doc)
    return strip_id(doc)

@api.delete("/comments/{item_id}")
async def delete_comment(item_id: str, _: dict = Depends(admin_only)):
    await db.comments.delete_one({"id": item_id})
    return {"success": True}

# ---------- Reports ----------
@api.post("/reports")
async def create_report(item: ReportCreate, user=Depends(require_user)):
    doc = {"id": uid(), **item.model_dump(), "reported_by": user["nickname"], "reported_by_id": user["id"], "status": "Pendente", "created_at": now()}
    await db.reports.insert_one(doc)
    return strip_id(doc)

@api.get("/reports")
async def reports(_: dict = Depends(admin_only)): return await many("reports")

@api.patch("/reports/{item_id}")
async def resolve_report(item_id: str, status: str, _: dict = Depends(admin_only)):
    await db.reports.update_one({"id": item_id}, {"$set": {"status": status, "resolved_at": now()}})
    return await db.reports.find_one({"id": item_id}, {"_id": 0})

# ---------- Polls ----------
@api.post("/polls/{poll_id}/vote")
async def vote_poll(poll_id: str, option_index: int, user=Depends(require_user)):
    key = f"poll:{poll_id}:{user['id']}"
    if await db.votes.find_one({"key": key}): raise HTTPException(400, "Você já votou nessa enquete.")
    poll = await db.polls.find_one({"id": poll_id}, {"_id": 0})
    if not poll or option_index not in range(len(poll["options"])): raise HTTPException(400, "Opção inválida.")
    await db.votes.insert_one({"key": key, "user_id": user["id"], "target_id": poll_id, "created_at": now()})
    options = poll["options"]
    options[option_index]["votes"] += 1
    await db.polls.update_one({"id": poll_id}, {"$set": {"options": options}})
    return await db.polls.find_one({"id": poll_id}, {"_id": 0})

# ---------- Admin: Users ----------
@api.get("/admin/users")
async def admin_users(_: dict = Depends(admin_only)):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(5000)
    return users

@api.get("/admin/users/export")
async def admin_export(fmt: str = "csv", _: dict = Depends(admin_only)):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(5000)
    fmt = fmt.lower()
    if fmt not in {"csv", "txt"}: raise HTTPException(400, "Formato inválido. Use csv ou txt.")
    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["id", "email", "nickname", "role", "is_verified", "creation_ip", "last_ip", "created_at", "last_login"])
        for u in users:
            writer.writerow([u.get("id",""), u.get("email",""), u.get("nickname",""), u.get("role",""), u.get("is_verified",False), u.get("creation_ip",""), u.get("last_ip",""), u.get("created_at",""), u.get("last_login","")])
        content = buf.getvalue()
        media = "text/csv"
    else:
        lines = ["# NETHZZZZ HQ - export de contas (sem senhas)"]
        for u in users:
            lines.append(f"{u.get('email','')} | {u.get('nickname','')} | criado_em={u.get('created_at','')} | ip_criacao={u.get('creation_ip','')} | ultimo_ip={u.get('last_ip','')} | ultimo_login={u.get('last_login','')}")
        content = "\n".join(lines)
        media = "text/plain"
    return StreamingResponse(iter([content]), media_type=media, headers={"Content-Disposition": f"attachment; filename=nethzzzz-users.{fmt}"})

@api.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: str, _: dict = Depends(admin_only)):
    await db.users.delete_one({"id": user_id})
    return {"success": True}

app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=[os.environ["FRONTEND_URL"]], allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return resp

logging.basicConfig(level=logging.INFO)
