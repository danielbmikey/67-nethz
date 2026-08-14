from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
import logging, os, uuid, bcrypt, jwt
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, ConfigDict

load_dotenv(Path(__file__).parent / ".env")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ["JWT_SECRET"]
ADMIN_EMAIL = os.environ["ADMIN_EMAIL"].lower()
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]
now = lambda: datetime.now(timezone.utc).isoformat()

def uid(): return str(uuid.uuid4())
def token_for(email): return jwt.encode({"sub": email, "role": "admin", "exp": datetime.now(timezone.utc).timestamp() + 86400}, JWT_SECRET, algorithm="HS256")

async def admin_only(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        header = request.headers.get("Authorization", "")
        token = header[7:] if header.startswith("Bearer ") else None
    if not token: raise HTTPException(401, "Faça login para moderar.")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        if payload.get("sub") != ADMIN_EMAIL: raise HTTPException(403, "Acesso restrito ao streamer.")
        return payload
    except jwt.PyJWTError: raise HTTPException(401, "Sessão expirada.")

class GameCreate(BaseModel): title: str; genre: str; description: str; platform: str = "PC"; submitted_by: str = "Anônimo"
class ClipCreate(BaseModel): title: str; url: str; clip_type: str = "link"; submitted_by: str = "Anônimo"
class CommentCreate(BaseModel): target_id: str; target_type: str; author: str; content: str
class ReportCreate(BaseModel): target_id: str; target_type: str; reason: str; reported_by: str = "Anônimo"
class PollCreate(BaseModel): question: str; options: List[str]
class ScheduleCreate(BaseModel): day: str; time: str; game: str; description: str; is_special: bool = False
class Login(BaseModel): email: str; password: str

@asynccontextmanager
async def lifespan(app):
    try:
        await db.admins.create_index("email", unique=True)
        admin = await db.admins.find_one({"email": ADMIN_EMAIL})
        hashed = bcrypt.hashpw(ADMIN_PASSWORD.encode(), bcrypt.gensalt()).decode()
        if not admin: await db.admins.insert_one({"email": ADMIN_EMAIL, "password_hash": hashed, "role": "admin"})
        elif not bcrypt.checkpw(ADMIN_PASSWORD.encode(), admin["password_hash"].encode()): await db.admins.update_one({"email": ADMIN_EMAIL}, {"$set": {"password_hash": hashed}})
        if await db.games.count_documents({}) == 0:
            await db.games.insert_many([
                {"id":uid(),"title":"Elden Ring: Nightreign","genre":"Souls-like / Co-op","description":"Neth tem que jogar com o chat gritando em cada boss fight!","platform":"PC","submitted_by":"ViciadoEmSouls","votes":42,"status":"Aprovado","marked_as_played":False,"created_at":now()},
                {"id":uid(),"title":"Phasmophobia (Modo Pesadelo)","genre":"Terror / Coop","description":"Leva os sustos ao vivo com o áudio estourado!","platform":"PC","submitted_by":"GhostHunter99","votes":35,"status":"Jogado","marked_as_played":True,"created_at":now()},
                {"id":uid(),"title":"Hollow Knight: Silksong","genre":"Metroidvania","description":"O jogo mais aguardado do século para o Neth sofrer.","platform":"PC","submitted_by":"SilkFanatic","votes":58,"status":"Analisando","marked_as_played":False,"created_at":now()}])
        if await db.clips.count_documents({}) == 0: await db.clips.insert_many([{"id":uid(),"title":"CLIPE DO SÉCULO: 1V5 Clutch de Vandal na bala!","url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","clip_type":"link","submitted_by":"ClutchMaster","likes":128,"created_at":now()},{"id":uid(),"title":"Neth rindo da própria desgraça no Jumpscare","url":"https://clips.twitch.tv/","clip_type":"link","submitted_by":"RisadaGarantida","likes":94,"created_at":now()}])
        if await db.schedule.count_documents({}) == 0: await db.schedule.insert_many([{"id":uid(),"day":"Segunda-feira","time":"19:00 BRT","game":"Valorant & Ranqueadas","description":"Subindo pro Imortal com o chat","is_special":False},{"id":uid(),"day":"Quarta-feira","time":"20:00 BRT","game":"Jogos Sugeridos pelo Chat","description":"Testando as melhores sugestões da comunidade!","is_special":True},{"id":uid(),"day":"Sexta-feira","time":"21:00 BRT","game":"Terror & Sustos","description":"Noite de cagaço coletivo","is_special":False}])
        if await db.polls.count_documents({}) == 0: await db.polls.insert_one({"id":uid(),"question":"Qual jogo o Neth deve zerar na maratona de 12 horas?","options":[{"text":"Dark Souls 3 sem tomar hit","votes":45},{"text":"Outlast Trials Hardcore","votes":30},{"text":"GTA San Andreas Chaos Mod","votes":82}],"is_active":True,"created_at":now()})
    except Exception as exc: logging.error("Seed warning: %s", exc)
    yield
    client.close()

app = FastAPI(title="Nethzzzz Community HQ", lifespan=lifespan)
api = APIRouter(prefix="/api")
async def many(collection): return await db[collection].find({}, {"_id":0}).to_list(1000)

@api.get("/")
async def root(): return {"message":"API do @nethzzzz operando"}
@api.get("/games")
async def games(): return await many("games")
@api.post("/games")
async def create_game(item: GameCreate):
    doc={"id":uid(),**item.model_dump(),"votes":0,"status":"Pendente","marked_as_played":False,"created_at":now()}; await db.games.insert_one(doc); return {k:v for k,v in doc.items() if k != "_id"}
@api.post("/games/{item_id}/vote")
async def vote_game(item_id: str):
    await db.games.update_one({"id": item_id}, {"$inc": {"votes": 1}})
    item = await db.games.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(404, "Jogo não encontrado")
    return item
@api.patch("/games/{item_id}/status")
async def status_game(item_id: str, status: str, marked_as_played: Optional[bool]=None, _: dict=Depends(admin_only)):
    update={"status":status}
    if marked_as_played is not None: update["marked_as_played"]=marked_as_played
    await db.games.update_one({"id":item_id},{"$set":update}); return await db.games.find_one({"id":item_id},{"_id":0})
@api.get("/clips")
async def clips(): return await many("clips")
@api.post("/clips")
async def create_clip(item: ClipCreate):
    doc={"id":uid(),**item.model_dump(),"likes":0,"created_at":now()}
    await db.clips.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}
@api.post("/clips/{item_id}/like")
async def like_clip(item_id: str):
    await db.clips.update_one({"id":item_id},{"$inc":{"likes":1}}); return await db.clips.find_one({"id":item_id},{"_id":0})
@api.get("/comments/{target_id}")
async def comments(target_id: str): return await db.comments.find({"target_id":target_id},{"_id":0}).to_list(1000)
@api.post("/comments")
async def create_comment(item: CommentCreate):
    doc={"id":uid(),**item.model_dump(),"created_at":now()}
    await db.comments.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}
@api.post("/reports")
async def create_report(item: ReportCreate):
    doc={"id":uid(),**item.model_dump(),"status":"Pendente","created_at":now()}; await db.reports.insert_one(doc); return doc
@api.get("/reports")
async def reports(_: dict=Depends(admin_only)): return await many("reports")
@api.get("/polls")
async def polls(): return await many("polls")
@api.post("/polls/{poll_id}/vote")
async def vote_poll(poll_id: str, option_index: int):
    poll=await db.polls.find_one({"id":poll_id},{"_id":0})
    if not poll or option_index not in range(len(poll["options"])): raise HTTPException(400,"Opção inválida")
    options=poll["options"]; options[option_index]["votes"]+=1; await db.polls.update_one({"id":poll_id},{"$set":{"options":options}}); return await db.polls.find_one({"id":poll_id},{"_id":0})
@api.get("/schedule")
async def schedule(): return await many("schedule")
@api.post("/auth/login")
async def login(item: Login, response: Response):
    admin=await db.admins.find_one({"email":item.email.lower()})
    if not admin or not bcrypt.checkpw(item.password.encode(),admin["password_hash"].encode()): raise HTTPException(401,"Email ou senha incorretos.")
    token=token_for(ADMIN_EMAIL); response.set_cookie("access_token",token,httponly=True,secure=True,samesite="none",max_age=86400); return {"email":ADMIN_EMAIL,"role":"admin","token":token}
@api.get("/auth/me")
async def me(_: dict=Depends(admin_only)): return {"email":ADMIN_EMAIL,"role":"admin"}
@api.post("/auth/logout")
async def logout(response: Response): response.delete_cookie("access_token"); return {"success":True}

app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=[os.environ["FRONTEND_URL"]], allow_methods=["*"], allow_headers=["*"])
logging.basicConfig(level=logging.INFO)