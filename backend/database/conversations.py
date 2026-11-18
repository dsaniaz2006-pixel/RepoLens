"""Persistent, owner-scoped chats. SQLAlchemy supports SQLite or PostgreSQL."""
import os
import time
import uuid
from functools import lru_cache
from pathlib import Path
from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, Float, Text, JSON, select, update, delete, inspect, text, and_, or_
from fastapi import HTTPException

metadata = MetaData()
chats = Table('conversations', metadata,
    Column('id', String(36), primary_key=True), Column('owner', String(128), nullable=False, index=True),
    Column('repository', String(256), nullable=False), Column('revision', String(40), nullable=False),
    Column('workspace_id', String(36), nullable=True),
    Column('title', String(120), nullable=False), Column('updated', Float, nullable=False),
    Column('version', Integer, nullable=False, default=0), Column('lease', String(36)), Column('lease_until', Float))
messages = Table('conversation_messages', metadata,
    Column('id', String(36), primary_key=True), Column('conversation_id', String(36), nullable=False, index=True),
    Column('position', Integer, nullable=False), Column('role', String(16), nullable=False),
    Column('content', Text, nullable=False), Column('citations', JSON, nullable=False), Column('uncertain', Integer, nullable=False))

class ConversationStore:
    def __init__(self, url):
        self.engine = create_engine(url, **({'connect_args': {'timeout': 30}} if url.startswith('sqlite:') else {}))
        # Conversation listing checks current workspace membership. Declare
        # that table before schema creation, even when this store is the
        # first database component initialized in a fresh installation.
        from backend.database.product_store import members  # noqa: F401
        metadata.create_all(self.engine)
        # Existing Phase 0 installations already have the conversations table.
        # create_all() does not add new columns; migrate in place without
        # discarding saved conversations or changing their owner/revision.
        if 'workspace_id' not in {col['name'] for col in inspect(self.engine).get_columns('conversations')}:
            with self.engine.begin() as connection:
                connection.execute(text('ALTER TABLE conversations ADD COLUMN workspace_id VARCHAR(36)'))

    @staticmethod
    def require_workspace_membership(connection, user, wid):
        if not wid:
            return
        from backend.database.product_store import members
        member = connection.execute(select(members.c.role).where(
            members.c.workspace == wid, members.c.user == user)).first()
        if not member:
            # Avoid exposing whether a removed or private workspace exists.
            raise HTTPException(404, 'Conversation not found')

    def owned(self, connection, owner, cid):
        row = connection.execute(select(chats).where(chats.c.id == cid, chats.c.owner == owner)).mappings().first()
        if not row: raise HTTPException(404, 'Conversation not found')
        self.require_workspace_membership(connection, owner, row['workspace_id'])
        return dict(row)

    def create(self, owner, repo, revision, *, workspace_id=None):
        row = dict(id=str(uuid.uuid4()), owner=owner, repository=repo, revision=revision, workspace_id=workspace_id,
                   title=repo, updated=time.time(), version=0, lease=None, lease_until=None)
        with self.engine.begin() as conn:
            self.require_workspace_membership(conn, owner, workspace_id)
            conn.execute(chats.insert().values(**row))
        return self.get(owner, row['id'])

    def listing(self, owner):
        # Filter revoked workspace chats BEFORE pagination. Otherwise 100 old
        # revoked threads could push the user's personal chats out of view.
        from backend.database.product_store import members
        query=(select(chats)
               .outerjoin(members,and_(members.c.workspace==chats.c.workspace_id,
                                       members.c.user==owner))
               .where(chats.c.owner==owner,
                      or_(chats.c.workspace_id.is_(None),members.c.user.is_not(None)))
               .order_by(chats.c.updated.desc()).limit(100))
        with self.engine.connect() as conn:
            return [self.public(dict(row)) for row in conn.execute(query).mappings()]

    @staticmethod
    def public(row):
        return {k:v for k,v in row.items() if k not in ('owner','lease','lease_until')} | {'pending': bool(row['lease'] and (row['lease_until'] or 0)>time.time())}

    def get(self, owner, cid):
        with self.engine.connect() as conn:
            row=self.owned(conn,owner,cid)
            items=[dict(m) for m in conn.execute(select(messages).where(messages.c.conversation_id==cid).order_by(messages.c.position)).mappings()]
            return self.public(row) | {'messages':items}

    def remove(self, owner, cid):
        with self.engine.begin() as conn:
            self.owned(conn,owner,cid)
            conn.execute(delete(chats).where(chats.c.id==cid, chats.c.owner==owner))
            conn.execute(delete(messages).where(messages.c.conversation_id==cid))

    def begin(self, owner, cid, repo, version):
        token=str(uuid.uuid4()); now=time.time()
        with self.engine.begin() as conn:
            row=self.owned(conn,owner,cid)
            if row['repository']!=repo: raise HTTPException(400,'Conversation belongs to another repository')
            if version is None or row['version']!=version: raise HTTPException(409,'Conversation changed. Reload messages before sending.')
            if version>=200: raise HTTPException(400,'Start a new conversation after 100 answers.')
            result=conn.execute(update(chats).where(chats.c.id==cid,chats.c.version==version,
                (chats.c.lease==None)|(chats.c.lease_until<now)).values(lease=token,lease_until=now+300))
            if result.rowcount!=1: raise HTTPException(409,'An answer is already running. Reload shortly.')
            history=[dict(m) for m in conn.execute(select(messages).where(messages.c.conversation_id==cid).order_by(messages.c.position.desc()).limit(12)).mappings()][::-1]
        return row,token,history

    def referenced_turn(self, owner, cid, ordinal, version):
        """Read an ABSOLUTE prior question number from this owner's saved chat.

        Recent model context is capped at 12 messages. Its first user turn is
        therefore often not question 1; never re-number it after pagination.
        """
        if not isinstance(ordinal, int) or ordinal < 1 or ordinal * 2 > version:
            return None
        with self.engine.connect() as conn:
            row = self.owned(conn, owner, cid)
            if ordinal * 2 > row['version']:
                return None
            rows = [dict(m) for m in conn.execute(select(messages).where(
                messages.c.conversation_id == cid,
                messages.c.position.in_([ordinal * 2 - 1, ordinal * 2])
            ).order_by(messages.c.position)).mappings()]
            if len(rows) != 2 or rows[0]['role'] != 'user' or rows[1]['role'] != 'assistant':
                return None
            return rows

    def finish(self, cid, token, version, question, answer):
        with self.engine.begin() as conn:
            row=conn.execute(select(chats).where(chats.c.id==cid, chats.c.lease==token, chats.c.version==version)).mappings().first()
            if not row: raise HTTPException(409,'Conversation was deleted or its request expired. Reload messages.')
            self.require_workspace_membership(conn, row['owner'], row['workspace_id'])
            result=conn.execute(update(chats).where(chats.c.id==cid,chats.c.lease==token,chats.c.version==version).values(
                lease=None,lease_until=None,version=version+2,updated=time.time(),title=question[:120] if version==0 else chats.c.title))
            if result.rowcount!=1: raise HTTPException(409,'Conversation was deleted or its request expired. Reload messages.')
            for offset,role,content,citations,uncertain in [(1,'user',question,[],False),(2,'assistant',answer['answer'],answer['citations'],answer['uncertain'])]:
                conn.execute(messages.insert().values(id=str(uuid.uuid4()),conversation_id=cid,position=version+offset,role=role,content=content,citations=citations,uncertain=int(uncertain)))

    def release(self, cid, token):
        with self.engine.begin() as conn: conn.execute(update(chats).where(chats.c.id==cid,chats.c.lease==token).values(lease=None,lease_until=None))

@lru_cache(maxsize=16)
def store_for(url): return ConversationStore(url)

def request_store(request):
    directory=Path(request.app.state.auth.directory)
    directory.mkdir(parents=True,exist_ok=True)
    return store_for(os.environ.get('REPOLENS_DATABASE_URL') or 'sqlite:///'+str(directory/'conversations.sqlite3'))

def answer_turn(store, owner, cid, url, question, version):
    import backend.services.pipeline as pipeline
    owner_name,repo_name=pipeline.parse_github_url(url)
    row,token,history=store.begin(owner,cid,f'{owner_name}/{repo_name}'.lower(),version)
    try:
        # Earlier questions resolve pronouns; history is never treated as source evidence.
        from backend.rag.retriever import contextual_query, referenced_question_number
        ordinal = referenced_question_number(question)
        reference = store.referenced_turn(owner, cid, ordinal, row['version']) if ordinal else None
        retrieval_history = history
        if reference and ordinal > 1:
            # If a referenced question has a pronoun, its antecedent may lie
            # outside the recent 12-message window. Read only the same user's
            # preceding turn at this same immutable repository revision.
            earlier = store.referenced_turn(owner,cid,ordinal-1,row['version'])
            if earlier and all(m['position'] != earlier[0]['position'] for m in history):
                retrieval_history = earlier + history
        query=contextual_query(question,retrieval_history,referenced_turn=reference if ordinal else ...)
        chunks=pipeline.retrieve(row['repository'],row['revision'],query)
        # Include an old explicitly referenced turn inside the bounded model
        # context without changing the ordinary last-12-messages policy.
        model_history=history
        if reference and not any(m['position']==reference[0]['position'] for m in history):
            model_history=reference+history[-10:]
        answer=pipeline.answer_question(question,chunks,history=model_history)
        store.finish(cid,token,row['version'],question,answer)
        return store.get(owner,cid)
    finally: store.release(cid,token)
