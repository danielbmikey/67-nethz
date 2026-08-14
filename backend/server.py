from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
import csv, io, logging, os, re, uuid, bcrypt, jwt
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
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]
now = lambda: datetime.now(timezone.utc).isoformat()
NICK_RE = re.compile(r"^[A-Za-z0-9_.-]{3,24}$")

def uid(): return str(uuid.uuid4())
def strip_id(doc): return {k: v for k, v in doc.items() if k != "_id"} if doc else None
def token_for(sub, role): return jwt.encode({"sub": sub, "role": role, "exp": datetime.now(timezone.utc).timestamp() + 86400}, JWT_SECRET, algorithm="HS256")
def hash_pw(pw): return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
def check_pw(pw, hashed): return bcrypt.checkpw(pw.encode(), hashed.encode())
def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd: return fwd.split(",")[0].strip()
    real = request.headers.get("x-real-ip")
    return real or (request.client.host if request.client else "0.0.0.0")

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
    if not payload: raise HTTPException(401, "Faça login para moderar.")
    if payload.get("role") != "admin" or payload.get("sub") != ADMIN_EMAIL:
        raise HTTPException(403, "Acesso restrito ao streamer.")
    return payload

async def current_user(request: Request):
    payload = await decode_token(request)
    if not payload: return None
    if payload.get("role") == "admin": return {"id": "admin", "nickname": "STREAMER", "email": ADMIN_EMAIL, "role": "admin"}
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
class Login(BaseModel): email: str; password: str
class Signup(BaseModel): email: EmailStr; password: str = Field(min_length=6, max_length=72); nickname: str

@asynccontextmanager
async def lifespan(app):
    try:
        await db.admins.create_index("email", unique=True)
        await db.users.create_index("email", unique=True)
        await db.users.create_index("nickname", unique=True)
        admin = await db.admins.find_one({"email": ADMIN_EMAIL})
        hashed = hash_pw(ADMIN_PASSWORD)
        if not admin: await db.admins.insert_one({"email": ADMIN_EMAIL, "password_hash": hashed, "role": "admin"})
        elif not check_pw(ADMIN_PASSWORD, admin["password_hash"]): await db.admins.update_one({"email": ADMIN_EMAIL}, {"$set": {"password_hash": hashed}})
        if await db.games.count_documents({}) == 0:
            await db.games.insert_many([
                {"id":uid(),"title":"Elden Ring: Nightreign","genre":"Souls-like / Co-op","description":"Neth tem que jogar com o chat gritando em cada boss fight!","platform":"PC","submitted_by":"ViciadoEmSouls","votes":42,"status":"Aprovado","marked_as_played":False,"created_at":now()},
                {"id":uid(),"title":"Phasmophobia (Modo Pesadelo)","genre":"Terror / Coop","description":"Leva os sustos ao vivo com o áudio estourado!","platform":"PC","submitted_by":"GhostHunter99","votes":35,"status":"Jogado","marked_as_played":True,"created_at":now()},
                {"id":uid(),"title":"Hollow Knight: Silksong","genre":"Metroidvania","description":"O jogo mais aguardado do século para o Neth sofrer.","platform":"PC","submitted_by":"SilkFanatic","votes":58,"status":"Analisando","marked_as_played":False,"created_at":now()},
            ])
        if await db.clips.count_documents({}) == 0:
            await db.clips.insert_many([
                {"id":uid(),"title":"CLIPE DO SÉCULO: 1v5 clutch de vandal na bala","url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","clip_type":"link","submitted_by":"ClutchMaster","likes":128,"created_at":now()},
                {"id":uid(),"title":"Neth rindo da própria desgraça no jumpscare","url":"https://clips.twitch.tv/","clip_type":"link","submitted_by":"RisadaGarantida","likes":94,"created_at":now()},
            ])
        if await db.schedule.count_documents({}) == 0:
            await db.schedule.insert_many([
                {"id":uid(),"day":"Segunda-feira","time":"19:00 BRT","game":"Valorant & Ranqueadas","description":"Subindo pro Imortal com o chat","is_special":False},
                {"id":uid(),"day":"Quarta-feira","time":"20:00 BRT","game":"Jogos Sugeridos pelo Chat","description":"Testando as melhores sugestões da comunidade!","is_special":True},
                {"id":uid(),"day":"Sexta-feira","time":"21:00 BRT","game":"Terror & Sustos","description":"Noite de cagaço coletivo","is_special":False},
            ])
        if await db.polls.count_documents({}) == 0:
            await db.polls.insert_one({"id":uid(),"question":"Qual jogo o Neth deve zerar na maratona de 12 horas?","options":[{"text":"Dark Souls 3 sem tomar hit","votes":45},{"text":"Outlast Trials Hardcore","votes":30},{"text":"GTA San Andreas Chaos Mod","votes":82}],"is_active":True,"created_at":now()})
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
    token = token_for(user["id"], "viewer")
    response.set_cookie("access_token", token, httponly=True, secure=True, samesite="none", max_age=86400)
    return {"id": user["id"], "email": email, "nickname": nickname, "role": "viewer", "token": token}

@api.post("/auth/login")
async def login(item: Login, request: Request, response: Response):
    email = item.email.lower().strip()
    ip = client_ip(request)
    admin = await db.admins.find_one({"email": email})
    if admin and check_pw(item.password, admin["password_hash"]):
        token = token_for(ADMIN_EMAIL, "admin")
        response.set_cookie("access_token", token, httponly=True, secure=True, samesite="none", max_age=86400)
        return {"email": ADMIN_EMAIL, "nickname": "STREAMER", "role": "admin", "token": token}
    user = await db.users.find_one({"email": email})
    if not user or not check_pw(item.password, user["password_hash"]): raise HTTPException(401, "Email ou senha incorretos.")
    await db.users.update_one({"id": user["id"]}, {"$set": {"last_ip": ip, "last_login": now()}})
    token = token_for(user["id"], "viewer")
    response.set_cookie("access_token", token, httponly=True, secure=True, samesite="none", max_age=86400)
    return {"id": user["id"], "email": email, "nickname": user["nickname"], "role": "viewer", "token": token}

@api.get("/auth/me")
async def me(user=Depends(require_user)): return user

@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"success": True}

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
logging.basicConfig(level=logging.INFO)
